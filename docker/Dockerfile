FROM python:3.7.4

ENV USER user
ENV HOME /home/${USER}
ENV APP_PATH ${HOME}/antiintuit

RUN pip install requests bs4 peewee pymysql psycopg2-binary graypy ujson && \
    groupadd -g 1000 ${USER} && \
    useradd -s /bin/false -g 1000 -u 1000 -Md ${HOME} ${USER} && \
    mkdir -p ${APP_PATH}

USER ${USER}
WORKDIR ${HOME}

COPY --chown=${USER}:${USER} antiintuit ${APP_PATH}/