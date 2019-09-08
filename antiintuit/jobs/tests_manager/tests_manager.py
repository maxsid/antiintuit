import re
from datetime import timedelta

from bs4 import BeautifulSoup
from peewee import fn, JOIN, SQL
from requests import Session

from antiintuit.config import Config
from antiintuit.database import Account, Course, Subscribe, Test
from antiintuit.jobs.accounts_manager import get_authorized_session
from antiintuit.jobs.courses_manager import subscribe_to_course
from antiintuit.logger import exception, get_logger

__all__ = [
    "run_job",
    "get_publish_id_from_link"
]

logger = get_logger("antiintuit", "tests_manager")


@exception(logger)
def run_job():
    # Getting the tests of the first found course
    course = (Course
              .select()
              .order_by(Course.last_scan_at)
              .limit(1)).get()
    if course.last_scan_at > Config.get_course_scan_timeout_moment():
        next_in = course.last_scan_at - Config.get_course_scan_timeout_moment()
        logger.info("All courses in timeout. Timeout is %s. Next course is '%s' will be in %s.",
                    str(timedelta(minutes=Config.COURSE_SCAN_INTERVAL)).split(".")[0], str(course),
                    str(next_in).split(".")[0])
    else:
        logger.info("Selected '%s' course.", str(course))
        account, session = get_account_for_course(course).values()
        new_tests, found_tests = create_tests_of_course(course, account, session).values()
        logger.info("Tests result statistic:\n    Found tests - %i\n    New tests - %i",
                    found_tests, new_tests)
    appoint_accounts_for_tests()


def get_account_for_course(course: Course) -> dict:
    """Returns an account subscribed on a course and authorized session (or None)"""
    try:
        session = None
        account = (Account
                   .select()
                   .join(Subscribe)
                   .where((Account.reserved_until < Config.get_account_reserve_out_moment()) &
                          (Subscribe.course == course))
                   .order_by(Account.reserved_until)).get()
    except Account.DoesNotExist:
        account = (Account
                   .select(Account, fn.COUNT(Subscribe.id).alias("count"))
                   .join(Subscribe, JOIN.LEFT_OUTER, on=(Subscribe.account == Account.id))
                   .where(Account.reserved_until < Config.get_account_reserve_out_moment())
                   .group_by(Account.id)
                   .order_by("count", Account.reserved_until)).get()
        session = subscribe_to_course(account, course)
    return {"account": account, "session": session}


def get_publish_id_from_link(link: str) -> str:
    """Returns publish id of the test from a link."""
    return re.search(r"\d+/\d+/test/\d+/\d+", link).group()


def create_tests_of_course(course: Course, account: Account, session: Session = None) -> dict:
    """Adds tests of the course in database and updates dates"""
    session = session or get_authorized_session(account)
    info_page_response = session.get("{}/studies/courses/{}/info".format(Config.WEBSITE, course.publish_id),
                                     verify=Config.INTUIT_SSL_VERIFY)
    info_page_bs = BeautifulSoup(info_page_response.text, "html.parser")
    menu_bs = info_page_bs.find("ul", id="non-collapsible-item-1")
    new_tests_count, found_tests_count = 0, 0
    if menu_bs is not None:
        anchors_list_bs = menu_bs.find_all("a")
        for anchor in anchors_list_bs:
            if "/test/" in anchor["href"]:
                publish_test_id = get_publish_id_from_link(anchor["href"])
                questions_count = int(re.search(r"^\d+", anchor["title"]).group())
                title = anchor.text
                test = Test.get_or_none(publish_id=publish_test_id)
                if test is None:
                    test = Test.create(
                        publish_id=publish_test_id,
                        title=title,
                        course=course,
                        questions_count=questions_count)
                    logger.info("New test '%s' has added", str(test))
                    new_tests_count += 1
                else:
                    logger.debug("Test '%s' already exists", str(test))
                found_tests_count += 1
    else:
        logger.info("Course '%s' doesn't have the menu with links.", str(course))

    course.update_last_scan()
    return {"new": new_tests_count, "found": found_tests_count}


def appoint_accounts_for_tests():
    """Appoints watching accounts for tests without watchers"""
    tests = (Test
             .select()
             .where(Test.watcher.is_null())
             .order_by(Test.last_scan_at))
    for test in tests:
        course_watchers = (Test.
                           select(Test.watcher)
                           .where(Test.watcher.is_null(False) &
                                  (Test.course == test.course)))
        account = (Account
                   .select(Account, fn.COUNT(Test.id).alias("tests_count"))
                   .join(Test, JOIN.LEFT_OUTER, on=(Test.watcher_id == Account.id))
                   .where((Account.reserved_until < Config.get_account_reserve_out_moment()) &
                          (Account.id.not_in(course_watchers)))
                   .group_by(Account.id)
                   .order_by(SQL("`tests_count`"), Account.reserved_until)
                   .limit(1)).get()
        test.set_watcher(account)
        logger.info("Account '%s' appointed to watch for '%s' test.", str(account), str(test))
