import json
from datetime import datetime

from peewee import MySQLDatabase, PostgresqlDatabase, SqliteDatabase, Model, DateTimeField, TextField

from antiintuit.basic import truncate
from antiintuit.config import Config
from antiintuit.database.exceptions import DatabaseException
from antiintuit.logger import get_logger

__all__ = [
    "BaseModel",
    "VariantsModel"
]

logger = get_logger("antiintuit", "database")


def get_system_database():
    """Returns connection to database received from Config"""
    database_type = Config.DATABASE_TYPE.lower()
    logger.debug("Connection to %s database (%s)", database_type, Config.DATABASE_NAME)
    if database_type == "mysql":
        port = Config.DATABASE_PORT or 3306
        return MySQLDatabase(Config.DATABASE_NAME,
                             host=Config.DATABASE_HOST,
                             user=Config.DATABASE_USER,
                             password=Config.DATABASE_PASSWORD,
                             port=port,
                             charset="utf8mb4")
    elif database_type == "postgres":
        port = Config.DATABASE_PORT or 5432
        return PostgresqlDatabase(Config.DATABASE_NAME,
                                  host=Config.DATABASE_HOST,
                                  user=Config.DATABASE_USER,
                                  password=Config.DATABASE_PASSWORD,
                                  port=port)
    elif database_type == "sqlite":
        return SqliteDatabase(Config.DATABASE_NAME)
    else:
        raise DatabaseException("Supports sqlite, postgres or mysql(mariadb) databases, not '{}'".format(database_type))


class BaseModel(Model):
    created_at = DateTimeField(default=datetime.utcnow())

    def __str__(self):
        if hasattr(self, "describe"):
            return truncate(self.describe.replace("\n", "\\n"), 100)
        else:
            str(super())

    class Meta:
        database = get_system_database()


class VariantsModel(BaseModel):
    """Interface for a question and an answer classes"""
    _variants = TextField(help_text="The field contains a dict of variants in JSON as handled text")

    @property
    def variants(self) -> list:
        """Returns variants as list of handled text variants"""
        return json.loads(self._variants)

    @variants.setter
    def variants(self, variants: list):
        """Writes variants from list of handled text variants"""
        self._variants = json.dumps(variants, ensure_ascii=False)
