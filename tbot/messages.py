import aiogram.utils.markdown as md
import requests
from aiogram.types import ParseMode, Message, MediaGroup
from aiogram.utils.emoji import emojize

from tbot.arguments import config
from tbot.file_id_storage import file_id_storage
from tbot.photo_handlers import update_image_sources

__all__ = [
    "send_hello_message",
    "send_course_search_message",
    "send_that_not_found",
    "send_correct_number",
    "send_course_is_selected",
    "send_that_i_found",
    "send_right_answers",
]


async def get_enumerated_list(dicts_list: list, key: str, start_with=1):
    enumerated_list = list()
    for number, data_dict in enumerate(dicts_list, start_with):
        text = await update_image_sources(data_dict[key])
        enumerated_list.append(md.text(md.bold("/", number, sep=""), md.italic(text)))
    return enumerated_list


def get_ending(number: int or str) -> str:
    number_str = str(number)
    last_number = int(number_str[-1])
    if len(number_str) >= 2 and int(number_str[-2:]) in range(10, 20):
        return "ей"
    elif last_number in range(5, 10):
        return "ей"
    elif last_number in range(2, 5):
        return "и"
    elif last_number == 1:
        return "ь"
    elif last_number == 0:
        return "ей"


async def send_hello_message(message: Message):
    await message.reply(md.text(
        md.text("Привет ", message.from_user.first_name, "!", sep=""),
        md.text("Я бот АнтиИнтуит."),
        md.text("Я могу подсказать ответы на тесты или даже решить их за вас."),
        md.text("Начните поиск ответов c командой", md.bold("/course"))
    ), reply=False, parse_mode=ParseMode.MARKDOWN)


async def send_course_search_message(message: Message):
    await message.reply(md.text(
        md.text("Отправь"),
        md.bold("название курса"),
        md.text(", в котором ты хочешь искать вопросы, или его"),
        md.text(md.bold("URL"), ".", sep=""),
        md.text(emojize("Удачи! :wink:"))
    ), reply=False, parse_mode=ParseMode.MARKDOWN)


async def send_that_not_found(message: Message):
    await message.reply(md.bold(emojize("Ничего не найдено :see_no_evil:. Попробуйте еще!")),
                        reply=False, parse_mode=ParseMode.MARKDOWN)


async def send_correct_number(message: Message, data: dict, key: str, start_with=1):
    await message.reply(md.text(
        md.bold(emojize("Нужно отправить номер указанный в списке! :confounded:")),
        *await get_enumerated_list(data["data"], key, start_with),
        sep="\n"
    ), reply=False, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)


async def send_course_is_selected(message: Message, course: dict):
    await message.reply(md.text(
        md.text("Курс", md.bold(course["title"]), "выбран!"),
        md.text("Я буду искать вопросы только из этого курса, но ты можешь выбрать курс заново командой"),
        md.bold("/course.")), reply=False, parse_mode=ParseMode.MARKDOWN)


async def send_that_i_found(message: Message, data: dict, key: str, start_with=1):
    ending = get_ending(data["count"])
    await message.reply(md.text(
        md.text(emojize(":point_right: Я нашел"), md.bold(data["count"]), md.text("запис" + ending + ":")),
        *await get_enumerated_list(data["data"], key, start_with),
        sep="\n"
    ), reply=False, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)


async def send_right_answers(message: Message, question: dict):
    response = requests.get("{}/questions/{}/answers".format(config.host, question["id"]), params={"where:status": "R"})

    if response.status_code != 200:
        await message.reply(md.bold(emojize("К сожалению я пока не знаю ответа на этот вопрос :confused:")),
                            reply=False, parse_mode=ParseMode.MARKDOWN)
    else:
        media_group_content, right_answers_text, ps_message = list(), list(), ""
        title_text, title_photos = (await update_image_sources(question["title"], False)).values()
        media_group_content.extend(title_photos)

        answers = response.json()["data"][0]["variants"]
        for answer in answers:
            answer_text, answer_photos = (await update_image_sources(
                answer[-1], False, len(media_group_content))).values()
            right_answers_text.append(md.bold(emojize(":white_check_mark:"), answer_text))
            media_group_content.extend(answer_photos)
        if media_group_content:
            ps_message = md.text("\n", md.bold("P.S."), " Текст может не отображать полной информации из картинок,",
                                 " поэтому ниже я отправил изображения из теста.", sep="")

        await message.reply(md.text(
            md.text(emojize(":nerd_face: Я нашел ответ на вопрос:")),
            md.italic(title_text),
            *right_answers_text,
            ps_message,
            sep="\n"
        ), reply=False, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
        if media_group_content:
            media_group = MediaGroup()
            photos_map = map(lambda mgc: mgc[1], media_group_content)
            names_map = map(lambda mgc: mgc[0], media_group_content)
            media_group.attach_many(*photos_map)
            media_group_messages = await message.reply_media_group(media_group, reply=False)
            for photo_name, photo_message in zip(names_map, media_group_messages):
                if (await file_id_storage.get_file_id(photo_name)) is None:
                    await file_id_storage.set_file_id(photo_name, photo_message.photo[-1].file_id)
