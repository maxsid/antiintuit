from datetime import datetime, timedelta

from bs4 import BeautifulSoup
from requests import Session

# from antiintuit.config import Config

__all__ = [
    "get_session",
    "get_image_extension",
    "get_inner_html",
    "truncate",
    "sub_timedelta"
]


def get_session():
    """Returns session with necessary headers"""
    session = Session()
    session.headers.update({
        "Connection": "keep-alive",
        # "Origin": Config.WEBSITE,
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/69.0.3497.12 Safari/537.36",
        "Upgrade-Insecure-Requests": "1",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "ru-ru",
        "Host": "www.intuit.ru"
    })
    return session


def sub_timedelta(td: timedelta) -> datetime:
    """This's for to subtract timedelta from utcnow"""
    return datetime.utcnow() - td


def get_image_extension(content_type: str):
    """Returns image extension from content type"""
    extensions = {
        "image/bmp": "bmp",
        "image/png": "png",
        "image/gif": "gif",
        "image/jpeg": "jpg",
        "image/pjpeg": "jpg",
        "image/svg+xml": "svg",
        "image/tiff": "tiff",
        "image/vnd.microsoft.icon": "ico",
        "image/x-icon": "ico"
    }
    return extensions.get(content_type.lower(), "")


def get_inner_html(element: BeautifulSoup):
    """Handles contents and gets content of str type"""
    return "".join(map(str, element.contents))


def truncate(obj, nlen):
    """ Convert 'obj' to string and truncate if greater than length"""
    str_value = str(obj)
    if len(str_value) > nlen:
        return str_value[:nlen - 3] + '...'
    return str_value
