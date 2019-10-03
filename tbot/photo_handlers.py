import io
from string import Formatter

import requests
from aiogram.types import InputFile, InputMediaPhoto
from bs4 import BeautifulSoup

from tbot.arguments import config
from tbot.file_id_storage import file_id_storage

__all__ = [
    "update_image_sources"
]


def get_formatter_keys(text: str):
    return [i[1] for i in Formatter().parse(text) if i[1] is not None]


async def get_image_input_file(name: str, caption: str):
    file_id = await file_id_storage.get_file_id(name)
    if file_id is None:
        image_url = "{}/{}/{}".format(config.host, config.img_path, name)
        image_response = requests.get(image_url)
        assert image_response.status_code == 200, "Image is not found!"
        image = io.BytesIO(image_response.content)
        input_file = InputFile(image, name)
        input_media_photo = InputMediaPhoto(input_file, caption=caption)
    else:
        input_media_photo = InputMediaPhoto(file_id, file_id, caption)
    return input_media_photo


async def update_image_sources(text: str, only_alt=True, start_numerate_with=0) -> list or dict:
    bs, text_content, input_media_photos = BeautifulSoup(text, "html.parser"), list(), list()
    for element in bs.contents:
        image_name = None
        if element.name == "img" and element.has_attr("src"):
            image_name = get_formatter_keys(element["src"])
            image_name = image_name[0] if image_name else None
        alt = ""
        if image_name and element.has_attr("alt"):
            alt = element["alt"].replace("\\", "")
            if not only_alt:
                alt += " (Рис. {})".format(len(input_media_photos) + start_numerate_with + 1)
            text_content.append(alt)
        if image_name and not only_alt:
            input_media_photos.append((image_name, await get_image_input_file(image_name, alt)))
        elif image_name is None:
            text_content.append(str(element))
    if only_alt:
        return "".join(text_content)
    else:
        return {
            "text": "".join(text_content),
            "photos": input_media_photos
        }
