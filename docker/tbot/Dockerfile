FROM python:3.7.4

ENV USER user
ENV HOME /home/${USER}
ENV PYTHONPATH ${HOME}

RUN groupadd -g 1000 ${USER} && \
    useradd -s /bin/false -g 1000 -u 1000 -Nmd ${HOME} ${USER}

USER ${USER}
WORKDIR ${HOME}

ENV APP_PATH=${HOME}/tbot
RUN pip install uvloop ujson aiogram bs4 requests emoji aioredis --user  --no-warn-script-location && \
    mkdir -p ${APP_PATH}

COPY --chown=${USER}:${USER} * ${APP_PATH}/
CMD ["python", "tbot/bot.py"]