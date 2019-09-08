import logging
import sys

import graypy
import urllib3

from antiintuit.config import Config

__all__ = [
    "exception",
    "get_logger"
]


def setup_logger():
    urllib3.disable_warnings()
    logger = logging.getLogger("antiintuit")
    logger.setLevel(logging.DEBUG)
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.INFO)
    logger.addHandler(stdout_handler)

    if isinstance(Config.GRAYLOG_HOST, str):
        host_port_list = Config.GRAYLOG_HOST.split(":")
        graylog_handler = None
        if len(host_port_list) == 1:
            graylog_handler = graypy.GELFHTTPHandler(host_port_list[0], 12201)
        elif len(host_port_list) == 2:
            graylog_handler = graypy.GELFHTTPHandler(host_port_list[0], int(host_port_list[1]))
        if graylog_handler is not None:
            graylog_handler.setLevel(logging.DEBUG)
            logger.addHandler(graylog_handler)


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
