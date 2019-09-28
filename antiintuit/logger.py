import logging
import sys

import graypy
import urllib3

from antiintuit.basic import get_host_and_port, is_open_connection
from antiintuit.config import Config

__all__ = [
    "exception",
    "get_logger",
    "setup_logger"
]


def setup_logger(name: str = None, logger: logging.Logger = None, disable_urllib_warnings=True):
    if disable_urllib_warnings:
        urllib3.disable_warnings()
    if name is None and logger is None:
        logger = logging.getLogger("antiintuit")
    elif logger is None:
        logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.INFO)
    logger.addHandler(stdout_handler)

    if isinstance(Config.GRAYLOG_HOST, str):
        host, port = get_host_and_port(Config.GRAYLOG_HOST, 12201)
        if is_open_connection(host, port):
            graylog_handler = graypy.GELFHTTPHandler(host, port)
            graylog_handler.setLevel(logging.DEBUG)
            logger.addHandler(graylog_handler)
        else:
            logger.warning("No connection to GrayLog (%s:%i)", host, port)
            stdout_handler.setLevel(logging.DEBUG)
    return logger


def get_logger(*module_name: str):
    logger = logging.getLogger(".".join(module_name))
    logger_adapter = logging.LoggerAdapter(logger, {"session": Config.SESSION_ID})
    return logger_adapter


def exception(logger):
    """ A decorator that wraps the passed in function and logs exceptions should one occur """

    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as ex:
                logger.exception(ex)
                raise

        return wrapper

    return decorator


setup_logger()
