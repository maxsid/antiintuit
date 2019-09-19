import logging
import re
from datetime import datetime, timedelta
from hashlib import sha3_256
from os import environ, listdir, makedirs, urandom
from pathlib import Path

from antiintuit.basic import sub_timedelta
from antiintuit.config.exceptions import ConfigDirectoryIsNotExist

__all__ = [
    "Config"
]

logger = logging.getLogger("antiintuit.config_reader")


class Config:
    ACCOUNTS_COUNT = 300
    ACCOUNT_RESERVE_TIMEOUT = 15  # Minutes
    COURSE_SCAN_INTERVAL = 60 * 24 * 15  # Minutes
    DATABASE_HOST = None
    DATABASE_NAME = "database.db"
    DATABASE_PASSWORD = None
    DATABASE_PORT = None
    DATABASE_TYPE = "SQLite"
    DATABASE_USER = None
    INTERVAL_BETWEEN_QUESTIONS = 7  # Seconds (in tests_solver.wait_timeout)
    INTERVAL_BETWEEN_SESSION_CHECK = 5  # Seconds (in tests_solver.get_or_create_question)
    INTUIT_SSL_VERIFY = True
    GRAYLOG_HOST = None
    LATENCY_STEP_INCREASE_BETWEEN_SIMILAR_QUESTIONS = 5  # seconds
    MAX_ACCOUNT_AGE = 60 * 24 * 1000  # Minutes
    MAX_ITERATIONS_OF_RECEIVING_QUESTIONS = 300  # tests_solver.get_passed_questions_and_answers
    MAX_LATENCY_FOR_OUT_OF_SYNC = 30  # Seconds
    MAX_LATENCY_FOR_SESSION_CHECKS = 300  # Seconds (after this time question will be forcibly selected)
    SESSION_ID = sha3_256(urandom(256)).hexdigest()
    STATIC_DIRECTORY = "static"
    TEST_SCAN_INTERVAL = 900  # Seconds
    WEBSITE = "https://www.intuit.ru"

    @staticmethod
    def update():
        """Updates config from files and environment"""
        dict_config = get_user_config()
        for key, value in dict_config.items():
            setattr(Config, key, value)

    @classmethod
    def get_static_directory_path(cls):
        """Returns the static directory as Path type and create if it isn't exists"""
        path = Path(cls.STATIC_DIRECTORY)
        if not path.exists():
            makedirs(str(path))
        return path

    @classmethod
    def get_account_aging_moment(cls) -> datetime:
        """Returns datetime which contains a moment of the account aging"""
        return sub_timedelta(timedelta(minutes=cls.MAX_ACCOUNT_AGE))

    @classmethod
    def get_account_reserve_out_moment(cls) -> datetime:
        """Returns datetime which contains a moment of the account timeout"""
        return sub_timedelta(timedelta(minutes=cls.ACCOUNT_RESERVE_TIMEOUT))

    @classmethod
    def get_course_scan_timeout_moment(cls) -> datetime:
        """Returns datetime which contains a moment of the course update timeout"""
        return sub_timedelta(timedelta(minutes=cls.COURSE_SCAN_INTERVAL))

    @classmethod
    def get_test_scan_timeout_moment(cls) -> datetime:
        """Returns datetime a moment of the timeout gone"""
        return sub_timedelta(timedelta(seconds=cls.TEST_SCAN_INTERVAL))


def get_typed_value(value: str):
    """Executes typing a string value"""
    if not isinstance(value, str):
        return value
    elif value.lower() == "true":
        return True
    elif value.lower() == "false":
        return False
    elif value.isdigit():
        return int(value)
    elif re.match("^\d+?\.\d+?$", value) is not None:
        return float(value)
    else:
        return value


def get_config_from_files(directory: Path) -> dict:
    """Returns data from files inside the directory"""
    data = dict()
    for filename in filter(lambda fn: hasattr(Config, fn), listdir(str(directory))):
        with open("{}/{}".format(directory, filename), "r") as file:
            data.update({filename: get_typed_value(file.read())})
    return data


def get_user_config() -> dict:
    """Returns configuration records by some keys."""
    # Filling from files
    config_directories = environ.get("CONFIG_DIRECTORIES", None)
    files_config = dict()
    if type(config_directories) is str:
        for config_directory in config_directories.split(";"):
            config_directory = Path(config_directory)
            if not config_directory.exists():
                raise ConfigDirectoryIsNotExist("Config directory {} is not exist.".format(config_directory))
            files_config.update(get_config_from_files(config_directory))
            logger.debug("Config has read from directory {}".format(config_directory))
    # Filling from environment
    environ_config = dict()
    filtered_config = filter(lambda fn: hasattr(Config, fn[0]), environ.items())
    for key, value in filtered_config:
        if key not in files_config:
            environ_config.update({key: get_typed_value(value)})
    if environ_config:
        logger.debug("Config has read from environment.")

    return {**environ_config, **files_config}


Config.update()
