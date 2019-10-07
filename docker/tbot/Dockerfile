FROM maxsid/antiintuit:core

ENV APP_PATH=${HOME}/tbot
RUN pip install uvloop ujson aiogram bs4 requests emoji aioredis --user  --no-warn-script-location

COPY --chown=${USER}:${USER} . ${APP_PATH}/
CMD ["python", "tbot/bot.py"]