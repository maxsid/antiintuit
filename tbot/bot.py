import logging

import requests
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.redis import RedisStorage2
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

from tbot.arguments import config
from tbot.basic import *
from tbot.messages import *

logging.basicConfig(level=logging.DEBUG)
bot = Bot(token=config.token)
storage = RedisStorage2(config.redis_host, config.redis_port, db=5)
dp = Dispatcher(bot, storage=storage)


class SearchForm(StatesGroup):
    course = State()
    question = State()


@dp.message_handler(commands=["start", "help"])
async def send_welcome(message: types.Message):
    await send_hello_message(message)


@dp.message_handler(state="*", commands=["course"])
async def start_course_search(message: types.Message):
    await types.ChatActions.typing(1)
    await SearchForm.course.set()
    await send_course_search_message(message)


@dp.message_handler(regexp=r"(https:\/\/|http:\/\/)?(www\.)?intuit\.ru\/studies\/courses\/.*", state=SearchForm.course)
async def search_course_by_url(message: types.Message, state: FSMContext):
    await types.ChatActions.typing(1)
    response = requests.get("{}/courses".format(config.host), params={"url": message.text})
    if response.status_code != 200:
        await send_that_not_found(message)
    else:
        course = response.json()["data"][0]
        async with state.proxy() as data:
            data["course"] = course
        await SearchForm.question.set()
        await send_course_is_selected(message, course)


@dp.message_handler(message_is_not_digit, state=SearchForm.course)
async def search_course_by_title(message: types.Message, state: FSMContext):
    await types.ChatActions.typing(1)
    response = requests.get("{}/courses".format(config.host), params={"where:like:title": message.text})
    if response.status_code != 200:
        await send_that_not_found(message)
    else:
        response_data = response.json()
        if response_data["count"] == 1:
            course = response_data["data"][0]
            async with state.proxy() as data:
                data["course"] = course
            await SearchForm.question.set()
            await send_course_is_selected(message, course)
        else:
            async with state.proxy() as data:
                data["course"] = response_data
            await send_that_i_found(message, response_data, "title")


@dp.message_handler(message_is_not_digit, state=SearchForm.question)
async def search_question_by_title(message: types.Message, state: FSMContext):
    await types.ChatActions.typing(1)
    async with state.proxy() as data:
        response = requests.get("{}/courses/{}/questions".format(config.host, data["course"]["id"]),
                                params={"where:like:title": message.text})
        if response.status_code != 200:
            await send_that_not_found(message)
        else:
            response_data = response.json()
            if response_data["count"] == 1:
                await send_right_answers(message, response_data["data"][0])
            else:
                await send_that_i_found(message, response_data, "title")
                data["question"] = response_data


@dp.message_handler(message_is_digit, state=SearchForm.course)
async def search_course_by_number(message: types.Message, state: FSMContext):
    await types.ChatActions.typing(1)
    variant = get_number(message.text)
    async with state.proxy() as data:
        response_data = data.get("course", None)
        if not isinstance(response_data, dict):
            await search_course_by_title(message, state)
        elif len(response_data["data"]) <= variant:
            await send_correct_number(message, response_data, "title")
        else:
            course = response_data["data"][variant]
            data["course"] = course
            await SearchForm.question.set()
            await send_course_is_selected(message, course)


@dp.message_handler(message_is_digit, state=SearchForm.question)
async def search_question_by_number(message: types.Message, state: FSMContext):
    await types.ChatActions.typing(1)
    variant = get_number(message.text)
    async with state.proxy() as data:
        response_data = data.get("question", None)
        if not isinstance(response_data, dict):
            await search_question_by_title(message, state)
        elif len(response_data["data"]) <= variant:
            await send_correct_number(message, response_data, "title")
        else:
            question = response_data["data"][variant]
            await send_right_answers(message, question)


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
