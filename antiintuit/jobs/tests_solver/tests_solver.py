import random
import re
from datetime import datetime, timedelta
from hashlib import sha3_256
from itertools import combinations
from time import sleep

import peewee
import requests
from bs4 import BeautifulSoup
from peewee import SQL
from requests import Session

from antiintuit.basic import get_image_extension
from antiintuit.config import Config
from antiintuit.database import *
from antiintuit.jobs.accounts_manager import get_authorized_session
from antiintuit.jobs.courses_manager import subscribe_to_course
from antiintuit.jobs.tests_manager import get_publish_id_from_link
from antiintuit.jobs.tests_solver.exceptions import *
from antiintuit.logger import exception, get_logger

__all__ = [
    "run_job"
]

logger = get_logger("antiintuit", "tests_solver")


@exception(logger)
def run_job():
    """Get a test and pass it"""
    test_course_account, session = None, None
    try:
        test_course_account = get_test_course_account()
        session = get_authorized_session(test_course_account["account"])
        pass_test(test_course_account, session)
    except TestIsTemporarilyUnavailableForPassByAccount as ex:
        account = test_course_account["account"]
        account.reserved_until = datetime.utcnow() + timedelta(minutes=ex.minutes_to_pass + 2)
        account.save()
        logger.warning(str(ex))
    except (CouldNotFindTest, TestIsAlreadySolved) as ex:
        logger.info(str(ex))
    except Exception:
        if test_course_account is not None:
            test, account = test_course_account["test"], test_course_account["account"]
            Question.unlock_all_session_question()
            if session is not None and isinstance(test, Test) and isinstance(account, Account):
                repeat_test(test, account, session)
        raise


def pass_test(test_course_account: dict, session: Session):
    """Pass test and update questions in database"""
    no_accept = True
    try:
        questions, answers = get_passed_questions_and_answers(session=session, **test_course_account).values()
    except NeedToPassAnotherTest as ex:
        no_accept, desired_test = False, test_course_account["test"]
        test_publish_id = get_publish_id_from_link(ex.course_link)
        test_course_account["test"] = Test.get(Test.publish_id == test_publish_id)
        logger.info("Before to pass '%s' test need to pass the test '%s'.", str(desired_test),
                    str(test_course_account["test"]))
        questions, answers = get_passed_questions_and_answers(session=session, **test_course_account).values()

    test, course, account = test_course_account.values()
    if test.questions_count != len(questions):
        logger.warning("Gave another number of the questions (%i, but must be %i). ",
                       len(questions), test.questions_count)
    else:
        logger.info("Test is finished and having %i questions.", len(questions))
    test_page_bs = get_test_page_bs(test.publish_id, session)
    is_test_passed, grade = update_answers(questions, answers, test_page_bs, session).values()
    logger.info("Test '%s' is%s passed with grade %i/100.", str(test), "" if is_test_passed else " not", grade)
    if not no_accept and is_test_passed:
        accept_test(test, account, session)
    else:
        repeat_test(test, account, session)
    test.update_stats(is_test_passed, grade)


def get_test_course_account():
    """Returns course and account of the first suitable test"""
    try:
        # sleeping random time for containers will be out of sync
        sleep_time = random.random() * Config.MAX_LATENCY_FOR_OUT_OF_SYNC
        logger.debug("Session '%s' is sleeping during %f", Config.SESSION_ID, sleep_time)
        sleep(sleep_time)
        test = (Test
                .select(Test,
                        (Test.average_rating * 5 + Test.passed_count * 3 + Test.not_passed_count).alias(
                            "passing_score"))
                .join(Account, on=(Account.id == Test.watcher))
                .where(Test.watcher.is_null(False) &
                       (Account.reserved_until < Config.get_account_reserve_out_moment()))
                .order_by(SQL("`passing_score`"), Test.average_rating, Test.last_scan_at, Test.created_at)
                .limit(1)).get()
        course, account = test.course, test.watcher
        account.reserve()
        logger.info("Selected '%s' test, '%s' course and '%s' account.", str(test), str(course), str(account))
        subscribe = Subscribe.get_or_none((Subscribe.account == account) & (Subscribe.course == course))
        if subscribe is None:
            logger.info("Account '%s' is not subscribed on '%s' course.", str(account), str(course))
            subscribe_to_course(account, course)
    except Test.DoesNotExist:
        raise CouldNotFindTest("Couldn't find test for solving.")

    return {
        "test": test,
        "course": course,
        "account": account
    }


def get_passed_questions_and_answers(test: Test, course: Course, account: Account, session: Session):
    """Returns questions and answers of the current test passing"""
    questions, answers = [], []
    post_data = start_test(test, course, account, session)

    for iteration in range(1, Config.MAX_ITERATIONS_OF_RECEIVING_QUESTIONS + 1):
        logger.debug("Question iteration: %i of %i", iteration, test.questions_count)
        if iteration == Config.MAX_ITERATIONS_OF_RECEIVING_QUESTIONS:
            raise MaxIterationsReached("For '{}' test iteration maximum number has been reached.")
        question_form_bs = get_question_form(post_data, session)
        if question_form_bs is None:
            break
        request_executed_at = datetime.utcnow()
        # Creating and getting question and answers
        question = get_or_create_question(question_form_bs, course)
        if question in questions:
            logger.warning("Question '%s' had been already in the questions list of the current passing.",
                           str(question))
            sleep(Config.INTERVAL_BETWEEN_QUESTIONS)
            continue
        answer = question.get_next_answer()
        if answer is None:
            logger.warning("Question '%s' doesn't have answers and they will be deleted and recreated.",
                           str(question))
            question.delete_answers()
            answer = generate_answers(question)[0]
        if isinstance(answer, Answer):
            logger.info("Answer '%s' (status: '%s') has been selected as answer on '%s' question.",
                        str(answer), answer.status, str(question))
        elif isinstance(answer, str):
            logger.info("Answer '%s' has been selected as answer on '%s' question.",
                        answer, str(question))

        questions.append(question)
        answers.append(answer)

        # Reading form inputs and filling post data
        inputs_bs = question_form_bs.find_all("input")
        inputs = filter(lambda inp: inp.has_attr("type") and inp["type"] not in ("radio", "checkbox"), inputs_bs)
        post_data = dict(map(lambda inp: (inp["name"], inp["value"]), inputs))
        post_data.update(get_answer_for_post_request(answer, question))
        wait_timeout(request_executed_at)
    return {"questions": questions, "answers": answers}


def get_test_page_bs(test_publish_id: str, session: Session) -> BeautifulSoup:
    """Returns test page as BeautifulSoup"""
    test_url = "{}/studies/courses/{}".format(Config.WEBSITE, test_publish_id)
    test_page_response = session.get(test_url)
    test_page_bs = BeautifulSoup(test_page_response.text, "html.parser")
    return test_page_bs


def start_test(test: Test, course: Course, account: Account, session: Session) -> dict:
    """Starts to pass an test and returns post data for the first question"""
    test_page_bs = get_test_page_bs(test.publish_id, session)
    test_start_form_bs = test_page_bs.find("form", id="int-course-test-start-page-form")
    if test_start_form_bs is None:
        if "необходимо пройти все предыдущие тесты курса" in test_page_bs.text:
            test_to_pass_href = test_page_bs.find("div", {"class": "eoi"}).find("a")["href"]
            raise NeedToPassAnotherTest(test, test_to_pass_href)
        elif "Для прохождения теста вы должны записаться на курс!" in test_page_bs.text:
            raise AccountIsNotSubscribed("Account '{}' is not subscribed on '{}' course for pass of '{}' test."
                                         .format(str(account), str(course), str(test)))
        elif test_page_bs.find("table", id="test-results-table") is not None:
            raise TestIsAlreadySolved("Test '{}' is already solved by '{}'.".format(str(test), str(account)))
        raise TestSolverException("Under '{}' account couldn't find the start test form for '{}' test of '{}' course."
                                  .format(str(account), str(test), str(course)))
    post_data = dict(map(lambda inp: (inp["name"], inp["value"]), test_start_form_bs.find_all("input")))
    return post_data


def get_question_form(post_data: dict, session: Session) -> BeautifulSoup:
    """Returns a form of the question from a page"""
    question_json = session.post("{}/int_studies/json/callback_display_test_task".format(Config.WEBSITE),
                                 data=post_data).json()
    question_bs = BeautifulSoup(question_json["data"], "html.parser")
    question_form_bs = question_bs.find("form", id="test-task-form")
    if question_form_bs is None:
        error_bs = question_bs.find("div", {"class": "eoi"})
        if 'попытка сдачи теста будет доступна через' in error_bs.text:
            minutes_to_pass = int(re.search(r"\d+", error_bs.text).group())
            raise TestIsTemporarilyUnavailableForPassByAccount(minutes_to_pass)
        elif "Загрузка результатов тестирования" not in error_bs.text:
            raise TestSolverException("Incorrect error message: {}".format(error_bs.text))
    return question_form_bs


def get_or_create_question(question_form_bs: BeautifulSoup, course: Course) -> Question:
    """Finds a question by hash or create the new question if it not exist"""
    task_id = get_question_publish_id(question_form_bs)
    question = Question.get_or_none(Question.task_id == task_id)
    if question is None:
        logger.debug("Question %i not exists.", task_id)
        # Split question title and answers
        question_title_bs = question_form_bs.find("div", {"class": "question"})
        answers_bs = question_form_bs.find("div", {"class": "answer"})
        # Create question and answers
        question_title = get_handled_content(question_title_bs).strip()
        test_type = answers_bs.find("input", {"name": "test_type"})["value"].strip()
        if test_type in ("multiple", "single"):
            variants_list = get_variants_list(answers_bs)
        else:
            variants_list = "no"
        try:
            question = Question.create(
                task_id=task_id,
                title=question_title,
                type=test_type,
                variants=variants_list,
                locked_by=Config.SESSION_ID,
                locked_at=datetime.utcnow(),
                course=course)
        except peewee.IntegrityError as ex:
            if ex.args[0] == 1062:
                return get_or_create_question(question_form_bs, course)
            raise
        if test_type in ("multiple", "single"):
            answers = generate_answers(question)
            logger.info("Question '%s' has been created with %i answers and locked by '%s'.", str(question),
                        len(answers), Config.SESSION_ID)
        else:
            logger.info("Question '%s' has been created without answers and locked by '%s'.", str(question),
                        Config.SESSION_ID)
    else:
        logger.debug("Question '%s' exists.", str(question))
        end_session_checks_datetime = datetime.utcnow() + timedelta(seconds=Config.MAX_LATENCY_FOR_SESSION_CHECKS)
        while question.locked_by is not None and question.locked_by != Config.SESSION_ID:
            time_left = end_session_checks_datetime - datetime.utcnow()
            if time_left <= timedelta():
                logger.warning("Question '%s' is locked too much time. Question will be forcibly selected.",
                               str(question))
                break
            logger.debug("Question '%s' is locked by another's SESSION_ID during '%s' yet. Waiting...",
                         str(question), str(time_left).split(".")[0])
            sleep(Config.INTERVAL_BETWEEN_SESSION_CHECK)
            question = Question.get_or_none(Question.task_id == task_id)
        if not question.is_right_answer_exists and question.type in ("multiple", "single"):
            logger.debug("Question doesn't have a right answer and will be locked by Session '%s'.", Config.SESSION_ID)
            question.lock()
    return question


def wait_timeout(started_at: datetime):
    """Wait pause between answers requests"""
    timeout = Config.INTERVAL_BETWEEN_QUESTIONS
    timeout_delta = (datetime.utcnow() - started_at)
    if timeout_delta < timedelta(seconds=timeout):
        time_for_sleep = timeout - timeout_delta.seconds
        if time_for_sleep <= 0:
            return
        sleep(time_for_sleep)


def generate_answers(question: Question):
    """Generates combinations of answers and records them in database"""
    variants, answers = question.variants, []
    max_combinations_range = 1
    if question.type == "multiple":
        max_combinations_range = len(variants)
    elif question.type != "single":
        raise IncorrectTestType("Question '{}' has incorrect '{}' type and system can't generate answers.".format(
            question.title, question.type))
    for range_size in range(1, max_combinations_range + 1):
        for answer_combination in combinations(variants, range_size):
            answers.append(Answer.create(variants=list(answer_combination), status="U", question=question))
    logger.debug("Generated %i answers for %s question.", len(answers), str(question))
    return answers


def get_answer_for_post_request(answer: Answer, question: Question = None) -> dict:
    """Returns post data of the answer"""
    question = question or answer.question_id
    if question.type == "multiple":
        return dict(
            map(lambda var: (var[1], var[0]), answer.variants)
        )
    elif question.type == "single":
        first_variant = answer.variants[0]
        return dict(variant=first_variant[0])
    elif question.type == "template":
        return dict(variant=answer)
    else:
        raise IncorrectTestType("Question '{}' has incorrect '{}' type and system can't send answers.".format(
            question.title, question.type))


def get_variants_list(answer_elements: BeautifulSoup) -> list:
    """Gets variants of answers and handle them"""
    answers_list = list()
    variants_labels_bs = answer_elements.find_all("label", {"class": "option"})
    for variant_label in variants_labels_bs:
        variant_bs = variant_label.find("span", {"class": "right"})
        variant_text = get_handled_content(variant_bs).strip()
        variant_for = variant_label["for"].strip()
        variant_number = int(re.search(r'\d+$', variant_for).group())
        answers_list.append((variant_number, variant_for, variant_text))
    answers_list.sort()
    logger.debug("Found %i variants of the question.", len(answers_list))
    return answers_list


def accept_test(test: Test, account: Account, session: Session):
    """Accept test result on the website"""
    ids = test.publish_id_numbers
    accept_url = "{}/int_studies/json/callback_accept_test".format(Config.WEBSITE)
    accept_post_data = {"iduniver_edu_prog": ids[0], "course_id": ids[1], "type": ids[2], "idtest": ids[3]}
    session.post(accept_url, accept_post_data)
    account.reserve()
    logger.info("Test '%s' is accepted on the website by '%s'.", str(test), str(account))


def repeat_test(test: Test, account: Account, session: Session):
    """Resets test result on the website"""
    ids = test.publish_id_numbers
    repeat_url = "{}/int_studies/json/callback_repeat_test".format(Config.WEBSITE)
    repeat_post_data = {"iduniver_edu_prog": ids[0], "course_id": ids[1], "type": ids[2], "idtest": ids[3]}
    session.post(repeat_url, repeat_post_data)
    account.reserve()
    logger.info("Test '%s' will be repeated on the website by '%s'.", str(test), str(account))


def get_question_publish_id(form: BeautifulSoup) -> int:
    """Returns a publish id from BeautifulSoup a question form"""
    data_div_bs = form.find("div", {"class": "spelling-content-entity test-content"})
    data_line = data_div_bs["data"]
    data = dict(map(lambda v: v.split("="), data_line.split("&")))
    return int(data["idtask_edi_eoi"])


def update_answers(questions: list, answers: list, test_page_bs: BeautifulSoup, session: Session) -> dict:
    """Updates answers statuses and returns True if test has passed"""
    results_answers_anchor = test_page_bs.find("a", {"destination_block_id": "course-test-dialog"})
    answers_results_post_data = dict(map(lambda v: v.split("="), results_answers_anchor["request_data"].split("&")))
    answers_results_url = "{}/int_studies/json/callback_display_test_task_list".format(Config.WEBSITE)
    answers_results_json = session.post(answers_results_url, answers_results_post_data).json()
    answers_results_bs = BeautifulSoup(answers_results_json["data"], "html.parser")
    test_task_list = answers_results_bs.find("div", id="test_task_list")
    right_answers_count = 0
    for question, answer in zip(questions, answers):
        # Checking id in an answers list and a question
        task_list_item_like = test_task_list.find("div", id="likit-control-task_likeit_{}".format(question.task_id))
        if task_list_item_like is None:
            logger.warning("Tasks list doesn't have '%s' question . Question will ignore.", str(question))
            continue
        task_list_item = task_list_item_like.parent.parent
        answer_span = task_list_item.find("span", {"class": "task_no"})
        if isinstance(answer, Answer) and "incorrect" in answer_span["class"]:
            answer.set_as_wrong()
            logger.info("Answer '%s' of '%s' question is incorrect.", str(answer), str(question))
            if question.unchanged_answers_count == 1:
                logger.debug("Question has the one unchecked answer. Previously it will be marked as right.")
                prev_answer = question.get_next_answer()
                prev_answer.set_as_right()
        elif isinstance(answer, Answer) and "correct" in answer_span["class"]:
            right_answers_count += 1
            if answer.status != "R":
                answer.set_as_right()
            logger.info("Answer '%s' of '%s' question is correct.", str(answer), str(question))
        elif isinstance(answer, str) and "incorrect" in answer_span["class"]:
            logger.info("Answer '%s' of '%s' question is incorrect.", answer, str(question))
        elif isinstance(answer, str) and "correct" in answer_span["class"]:
            right_answers_count += 1
            logger.info("Answer '%s' of '%s' question is correct.", answer, str(question))
    Question.unlock_all_session_question()
    results_table = test_page_bs.find("table", id="test-results-table")
    results_table_trs = results_table.find_all("td", {"class": "value"})
    passed_result_text = results_table_trs[-1].text
    if questions:
        grade = int(right_answers_count / len(questions) * 100)
        logger.debug("Grade (%i) has been gave from questions list.", grade)
    else:
        grade = int(re.search(r"^\d+", results_table_trs[-2].text).group())
        logger.debug("Grade (%i) has been gave from the result table of the test result page.", grade)
    return {"passed": "не сдан" not in passed_result_text, "grade": grade}


def get_handled_content(element: BeautifulSoup) -> str:
    """Reading html of a bs object, download files and update text"""
    content = ""
    for child in element.children:
        if child.name == "img":
            del child["style"]
            img_src = "{}{}".format(Config.WEBSITE, child["src"])
            img_response = requests.get(img_src, verify=Config.INTUIT_SSL_VERIFY)
            img_hash = sha3_256(img_response.content).hexdigest()
            img_name = "{}.{}".format(img_hash, get_image_extension(img_response.headers["Content-Type"]))
            img_path = Config.get_static_directory_path().joinpath(img_name)
            child["src"] = "{" + img_name + "}"
            if not img_path.exists():
                with img_path.open("wb") as image_file:
                    image_file.write(img_response.content)
                    logger.debug("Saved new image at '%s'.", str(img_path.absolute()))
            else:
                logger.debug("Image '%s' already exist.", str(img_path.absolute()))
        elif child.name is not None:
            child = child.text
        content += str(child)
    return content.strip()
