from datetime import datetime
from random import randint

from requests import Response

from antiintuit.basic import get_session
from antiintuit.jobs.accounts_manager.temp_mailbox.letter_interface import LetterInterface
from antiintuit.jobs.accounts_manager.temp_mailbox.mailbox_interface import MailboxInterface
from antiintuit.jobs.accounts_manager.temp_mailbox.services.mytemp_email.mytemp_email_exceptions \
    import MyTempEmailException
from antiintuit.logger import get_logger

__all__ = [
    "MyTempEmailLetter",
    "MyTempEmailMailbox"
]

logger = get_logger("antiintuit", "temp_mailbox", "mytemp_email")


class MyTempEmailMailbox(MailboxInterface):
    """The class for working with https://mytemp.email service"""

    def __init__(self):
        self._sid, self._session = randint(0, 10000000), get_session()
        self._start_timestamp = int(datetime.utcnow().timestamp() * 1000)
        self._task, self._email_hash, self._messages = 1, None, []
        self._session.headers.clear()
        self._session.headers.update({"Origin": "https://mytemp.email", "Connection": "keep-alive",
                                      "Accept": "application/json, text/plain, */*", "Host": "api.mytemp.email",
                                      "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                                                    "(KHTML, like Gecko) Chrome/69.0.3497.12 Safari/537.36",
                                      "Accept-Language": "ru-ru"})
        super().__init__()
        if not self._ping():
            raise MyTempEmailException("MyTempEmailMailbox._ping has received incorrect data.")

        self._init_mailbox()
        logger.info("MyTemp mailbox {} has been initialized".format(self.email))
        self.refresh()

    @property
    def default_request_data(self) -> dict:
        """Returns the default data for using the mailbox"""
        return {"sid": self._sid, "task": self._task,
                "tt": int(datetime.utcnow().timestamp() * 1000) - self._start_timestamp}

    def _request(self, command, params=None, data=None, method="get") -> Response:
        """This method is just executing requests and incrementing task"""
        data, params = data or {}, params or {}
        response = self._session.request(method, "{}/{}".format("https://api.mytemp.email/1", command),
                                         data=data, params=params)
        self._task += 1
        return response

    def _request_json(self, command, params=None, data=None, method="get") -> dict:
        """This method is just executing requests and incrementing task then return json data"""
        return self._request(command, params, data, method).json()

    def _ping(self) -> bool:
        """All default data is checked that it's correct"""
        json_response = self._request_json("ping", self.default_request_data)
        return "ts" in json_response and json_response.get("pong", 0) is 1 and json_response.get("task", 0) is 1

    def _init_mailbox(self):
        """The method create a mailbox on the server"""
        options_response = self._request("inbox/create", self.default_request_data, method="options", )
        if options_response.status_code != 204:
            raise MyTempEmailException("options requests inside MyTempEmailMailbox._init_mailbox "
                                       "has received an incorrect status code. {} instead 204"
                                       .format(options_response.status_code))
        mailbox_data = self._request_json("inbox/create", self.default_request_data, self.default_request_data,
                                          method="post")
        if "err" in mailbox_data:
            raise MyTempEmailException("Create mailbox error: {} - {}".format(mailbox_data["err"],
                                                                              mailbox_data["msg"]))
        self._email, self._email_hash = mailbox_data["inbox"], mailbox_data["hash"]

    def refresh(self) -> list:
        """The method upload messages from the website"""
        logger.debug("The messages, inside {} mailbox, is updating.".format(self.email))
        check_data = self._request_json("inbox/check", {"inbox": self.email, "hash": self._email_hash,
                                                        **self.default_request_data})
        eml_set = set(map(lambda e: e.eml, self.messages))
        new_emails = filter(lambda e: e["eml"] not in eml_set, check_data["emls"])
        for ne in new_emails:
            full_message = self._request_json("eml/get",
                                              {"eml": ne["eml"], "hash": ne["hash"],
                                               **self.default_request_data})
            m = MyTempEmailLetter(self.email, ne["from_address"], ne["from_name"], ne["subject"],
                                  full_message["body_html"], ne["eml"])
            self._messages.append(m)
            self._request("eml/destroy", {"eml": ne["eml"], **self.default_request_data})
        logger.debug("The messages has been updated. They is {} now (new is {})"
                     .format(len(self.messages), len(self.new_messages)))
        return self.messages

    def __del__(self):
        """The magic method deletes the mailbox on the website"""
        if self.email is not None:
            logger.debug("%s mailbox is deleting.", self.email)
            self._request("inbox/destroy", "options", {"inbox": self.email, "hash": self._email_hash,
                                                       **self.default_request_data})
            self._request("inbox/destroy", {"inbox": self.email, "hash": self._email_hash, **self.default_request_data},
                          {"inbox": self.email, "hash": self._email_hash}, "post")


class MyTempEmailLetter(LetterInterface):
    def __init__(self, recipient, sender_address, sender_name, subject, text, eml):
        super().__init__(recipient, sender_address, sender_name, subject, text)
        self._eml = eml

    @property
    def eml(self) -> str:
        return self._eml
