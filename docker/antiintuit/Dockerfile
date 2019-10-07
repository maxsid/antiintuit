FROM maxsid/antiintuit:core

ENV APP_PATH ${HOME}/antiintuit
RUN pip install requests bs4 peewee pymysql psycopg2-binary graypy ujson --user --no-warn-script-location

COPY --chown=${USER}:${USER} . ${APP_PATH}/