from itertools import islice
from pathlib import Path
from random import randint
from time import sleep

import requests
from bs4 import BeautifulSoup

from antiintuit.basic import get_session
from antiintuit.config import Config
from antiintuit.database import Account, DeletedAccount
from antiintuit.jobs.accounts_manager.exceptions import *
from antiintuit.jobs.accounts_manager.temp_mailbox import get_random_mailbox, TempMailBoxException
from antiintuit.logger import exception, get_logger

__all__ = [
    "get_authorized_session",
    "delete_account",
    "run_job"
]

logger = get_logger("antiintuit", "accounts_manager")


@exception(logger)
def run_job():
    """Create and delete one account by a condition."""
    the_oldest_accounts = (Account
                           .select()
                           .where((Account.created_at < Config.get_account_aging_moment())
                                  &
                                  (Account.reserved_until < Config.get_account_reserve_out_moment()))
                           .order_by(Account.created_at)
                           )
    the_oldest_accounts_count = the_oldest_accounts.count()

    the_fresh_accounts = (Account
                          .select()
                          .where(Account.created_at >= Config.get_account_aging_moment()))
    the_fresh_accounts_count = the_fresh_accounts.count()

    if the_fresh_accounts_count < Config.ACCOUNTS_COUNT:
        logger.info("Registration will execute because too less accounts (%i -> %i).", the_fresh_accounts_count,
                    Config.ACCOUNTS_COUNT)
        register_random_user()
    elif the_oldest_accounts_count > 0:
        logger.info("Account deleting will execute because database has older accounts (%i).",
                    the_oldest_accounts_count)
        delete_account(the_oldest_accounts.get())
    elif the_fresh_accounts_count > Config.ACCOUNTS_COUNT:
        logger.info("Account deleting will execute because database has older accounts (%i <- %i).",
                    Config.ACCOUNTS_COUNT, the_fresh_accounts_count)
        delete_account(the_fresh_accounts.get())
    else:
        logger.info("There are accounts amount is well (%i) and no older ones "
                    "so no needs to create or delete accounts", Config.ACCOUNTS_COUNT)


def get_random_data_record(file_path: Path, records_count: int) -> str:
    """Return a random line from file_path"""
    data_file_path = Path(__file__).parent.joinpath(file_path)
    with data_file_path.open("r") as names_file:
        return next(islice(names_file, randint(0, records_count - 1), None))[:-1]


def get_random_first_name() -> str:
    """Return a random name from data/first_names.csv file."""
    count_first_names = 27574
    data_file_path = Path("data/first_names.csv")
    return get_random_data_record(data_file_path, count_first_names)


def get_random_last_name() -> str:
    """Return a random name from data/last_names.csv file."""
    count_last_names = 146193
    data_file_path = Path("data/last_names.csv")
    return get_random_data_record(data_file_path, count_last_names)


def get_random_password(size=None) -> str:
    """Return a string contains random symbols of English alphabet and digits."""
    symbols = [
        *map(lambda i: chr(i + 97), range(26)),
        *map(lambda i: chr(i + 65), range(26)),
        *map(str, range(10))
    ]
    symbols_size = len(symbols)
    size = size or randint(8, 24)
    password_map = map(lambda _: symbols[randint(0, symbols_size - 1)], range(size))
    return "".join(password_map)


def get_form_hidden_data(session: requests.Session, url, form_id) -> dict:
    """Return dictionary with hidden data of the form."""
    page_response = session.get(url, verify=Config.INTUIT_SSL_VERIFY)
    page_bs = BeautifulSoup(page_response.text, "html.parser")
    form_bs = page_bs.find("form", id=form_id)
    hidden_inputs_bs = form_bs.find_all("input", {"type": "hidden"})
    hidden_data = dict(map(lambda hid: (hid["name"], hid["value"]), hidden_inputs_bs))
    return hidden_data


def get_form_register_hidden_data(session: requests.Session) -> dict:
    """Return dictionary with hidden data of the registration form."""
    hidden_data = get_form_hidden_data(session, Config.WEBSITE, "user-register")
    keys_have_to_be = ["timezone", "form_build_id", "form_id", "captcha_sid", "captcha_token"]
    if not all(map(lambda key: key in hidden_data, keys_have_to_be)):
        raise ReceivedDataIsNotFull("Not all hidden inputs received from an page.")
    return hidden_data


def get_form_login_hidden_data(session: requests.Session) -> dict:
    """Return dictionary with hidden data of the login form."""
    hidden_data = get_form_hidden_data(session, Config.WEBSITE, "user-login-form")
    keys_have_to_be = ["form_build_id", "form_id"]
    if not all(map(lambda key: key in hidden_data, keys_have_to_be)):
        raise ReceivedDataIsNotFull("Not all hidden inputs received from an page.")
    return hidden_data


def get_authorized_session(account: Account, session: requests.Session = None) -> requests.Session:
    """Login session by the account"""
    session = session or get_session()
    data = get_form_login_hidden_data(session)
    data.update({
        "name": account.email,
        "pass": account.password,
        "op": "Войти",
        "destination": "intuituser/userpage"
    })
    page_response = session.post("{}/intuit".format(Config.WEBSITE), verify=Config.INTUIT_SSL_VERIFY, data=data)
    response_bs = BeautifulSoup(page_response.text, "html.parser")
    title_bs = response_bs.find("title")
    if "Моя страница" not in title_bs.text:
        messages_error_bs = response_bs.find("div", {"class": "messages error"})
        error_message_html = str(messages_error_bs)
        if messages_error_bs is None:
            raise AuthorizationError(
                "Login has done is unsuccessfully for account '{}'. The Page doesn't have "
                "information about the finish login and error messages.".format(str(account)))
        if "электронный адрес или пароль не найдены" in error_message_html:
            delete_account(account, True)
            raise AuthorizationError("Password or email are incorrect. Account '{}' has deleted."
                                     .format(str(account)))
        elif "Вы удалили свой профиль" in error_message_html:
            delete_account(account, True)
            raise AuthorizationError("Account '{}' already deleted on the site. "
                                     "This account just has deleted from database."
                                     .format(str(account)))
    return session


def register_session(account: Account, session: requests.Session = None) -> requests.Session:
    """Execute an register session and return it"""
    logger.debug("A try to register account with data: '%s'.", str(account))
    session = session or get_session()
    data = get_form_register_hidden_data(session)
    data.update({
        "user_sirname": account.last_name,
        "user_name": account.first_name,
        "user_patronimic": "",
        "user_gender": "0",
        "mail": account.email,
        "pass": account.password,
        "user_country": "Россия ",
        "user_region": "",
        "user_city": "",
        "user_birthday[day]": "0",
        "user_birthday[month]": "0",
        "user_birthday[year]": "0",
        "rules_confirm": "0",
        "captcha_response": "",
        "op": "Регистрация"
    })
    page_response = session.post(Config.WEBSITE, verify=Config.INTUIT_SSL_VERIFY, data=data)
    response_bs = BeautifulSoup(page_response.text, "html.parser")
    title_bs = response_bs.find("title")
    if "Завершение регистрации" not in title_bs.text:
        raise OperationHasDoneUnsuccessfully("Registration has done is unsuccessfully. The Page doesn't have "
                                             "information about the finish registration.")
    logger.debug("Account '{}' has been logged".format(str(account)))
    return session


def register_random_user() -> Account:
    """Registration account with random data and write in database."""
    first_name, last_name = get_random_first_name(), get_random_last_name()
    password = get_random_password()
    mailbox_generator = get_random_mailbox()
    temp_mailbox, deleted_account, exists_account = None, True, True
    while deleted_account is not None or exists_account is not None:
        try:
            temp_mailbox = next(mailbox_generator)
            deleted_account = DeletedAccount.get_or_none(DeletedAccount.email == temp_mailbox.email)
            exists_account = Account.get_or_none(Account.email == temp_mailbox.email)
        except TempMailBoxException:
            deleted_account, exists_account = True, True

    email = temp_mailbox.email
    temp_mailbox.mark_all_messages_as_read()
    account = Account(last_name=last_name, first_name=first_name, password=password, email=email)
    session = register_session(account)

    logger.debug("A waiting to receive email.")
    intuit_message = None
    while intuit_message is None:
        sleep(1)
        temp_mailbox.refresh()
        for new_message in temp_mailbox.new_messages:
            if "intuit.ru" in new_message.subject.lower():
                intuit_message = new_message
                break

    logger.debug("Reading a confirmation message and finding a link.")
    message_body_html = intuit_message.text
    message_body_bs = BeautifulSoup(message_body_html, "html.parser")
    a_links = message_body_bs.find_all("a")
    a_confirm_link = None
    for a_link in a_links:
        if "reg_confirm" in a_link["href"]:
            a_confirm_link = a_link["href"]
            break
    if not a_confirm_link:
        raise RegistrationError("Couldn't find confirmation link in a confirmation message")
    # Splitting an http link
    a_confirm_link = a_confirm_link[a_confirm_link.find("http"):]
    logger.debug("The next confirmation link has been received: '%s'", a_confirm_link)
    # Account confirm
    session.get(a_confirm_link, verify=Config.INTUIT_SSL_VERIFY)
    account.save()
    logger.info("Account '%s' has been registered", str(account))
    return account


def delete_account(account: Account, database_only: bool = False):
    """Delete account in intuit and database."""
    if not database_only:
        session = get_authorized_session(account)
        session.post("{}/int_user/json/delete_myself".format(Config.WEBSITE), verify=Config.INTUIT_SSL_VERIFY)
    account.delete_instance(database_only)
    logger.info("Account '%s' has been deleted%s.", str(account), " (database only)" if database_only else "")
