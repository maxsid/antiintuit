from datetime import date
from itertools import count

from bs4 import BeautifulSoup
from requests import Session

from antiintuit.basic import get_session, get_publish_id_from_link
from antiintuit.config import Config
from antiintuit.database import Account, Course, Subscribe
from antiintuit.jobs.accounts_manager import get_authorized_session
from antiintuit.logger import exception, get_logger

__all__ = [
    "run_job",
    "subscribe_to_course"
]

logger = get_logger("antiintuit", "courses_manager")


@exception(logger)
def run_job():
    """Checks pages of the courses list and adds they in database."""
    new_courses, founded_courses = 0, 0
    for page_num in count():
        logger.debug("Scanning %i page...", page_num)
        scanned_courses_stats = create_courses_from_page(page_num)
        new_courses += scanned_courses_stats["new"]
        founded_courses += scanned_courses_stats["found"]
        logger.debug("Found on page %i courses among them %i are new.",
                     scanned_courses_stats["found"], scanned_courses_stats["new"])
        if scanned_courses_stats["found"] == 0:  # If the list is empty then pages have ended.
            break
    logger.info("Courses result:\n    found on pages - %i\n    added new ones in database - %i",
                founded_courses, new_courses)


def create_courses_from_page(page: int, session: Session = None) -> dict:
    """Creates courses on the courses page and returns the courses amount statistic as dict"""
    session = session or get_session()
    page_response = session.get("{}/studies/courses?idfilter=0&sort=11&sort_order=1&search_data=&"
                                "tab=4&_page={}".format(Config.WEBSITE, page), verify=Config.INTUIT_SSL_VERIFY)
    page_bs = BeautifulSoup(page_response.text, "html.parser")
    courses_elements = page_bs.find_all("div", {"class": "entities-showcase-list-item"})
    new_courses, found_courses = 0, len(courses_elements)
    for course_element in courses_elements:
        # Fill date
        date_text = course_element.find("div", {"class": "td date"}).text
        date_split = date_text.strip().split(".")[::-1]
        publish_course_date = date(*map(int, date_split))
        # Fill title and ids
        a_title_bs = course_element.find("div", {"class": "title td"}).find("a")
        title = a_title_bs.text
        if course_element.find("div", {"class": "file_elements"}).find_all("span")[2].text == "платный":
            logger.debug("Skip course '%s' on %i page because it's a paid.", title, page)
            continue
        publish_course_id = get_publish_id_from_link(a_title_bs["href"])
        if publish_course_id is None:
            continue
        course = Course.get_or_none(Course.publish_id == publish_course_id)
        if course is None:
            Course.create(publish_id=publish_course_id,
                          published_on=publish_course_date,
                          title=title)
            new_courses += 1
            logger.info("New course '%s' has added", str(course))
        else:
            logger.debug("Course '%s' is already exists.", str(course))

    return {"new": new_courses, "found": found_courses}


def subscribe_to_course(account: Account, course: Course, session: Session = None) -> Session:
    """Subscribe account to course"""
    session = session or get_authorized_session(account)
    info_page_response = session.get(course.link, verify=Config.INTUIT_SSL_VERIFY)
    info_page_bs = BeautifulSoup(info_page_response.text, "html.parser")
    subscribe_anchor_bs = info_page_bs.find("a", {"class": "red ajax-command-anchor"})
    request_data = subscribe_anchor_bs["request_data"].split("&")
    request_data_dict = dict(map(lambda record: record.split("="), request_data))
    # Getting a dialog page with the submit
    dialog_json = session.post("{}/int_studies/json/signin_free_dialog".format(Config.WEBSITE),
                               data=request_data_dict, verify=Config.INTUIT_SSL_VERIFY).json()
    dialog_page = dialog_json["data"]
    dialog_bs = BeautifulSoup(dialog_page, "html.parser")
    sign_in_form_bs = dialog_bs.find("form", {"action": "/int_studies/json/signin_free_dialog"})
    sign_in_form_inputs_bs = sign_in_form_bs.find_all("input")
    sign_in_data = dict(map(lambda inp: (inp["name"], inp["value"]), sign_in_form_inputs_bs))
    session.post("{}/int_studies/json/signin".format(Config.WEBSITE), data=sign_in_data,
                 verify=Config.INTUIT_SSL_VERIFY)
    if account.get_id() is not None:
        Subscribe.create(account=account, course=course)
    logger.info("Account '%s' has subscribed to '%s' course.", str(account), str(course))
    return session


def unsubscribe_from_course(subscribe: Subscribe, session: Session = None) -> Session:
    """Unsubscribe account to course"""
    course, account = subscribe.course, subscribe.account
    session = session or get_authorized_session(account)
    publish_id_numbers = course.publish_id_numbers
    unsubscribe_url = "{}/int_studies/json/signout".format(Config.WEBSITE)
    post_data = {"title": "<span+class=\"delete\"></span>Отписаться",
                 "type": publish_id_numbers[0], "identity": publish_id_numbers[1]}
    session.post(unsubscribe_url, post_data, verify=Config.INTUIT_SSL_VERIFY)
    subscribe.delete_instance()
    logger.info("Account '%s' has unsubscribed from '%s' course.", str(account), str(course))
    return session
