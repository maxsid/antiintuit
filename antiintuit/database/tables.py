import json
from datetime import datetime, timedelta

from peewee import (Model, CharField, ForeignKeyField, TextField, DateTimeField, MySQLDatabase,
                    SqliteDatabase, PostgresqlDatabase, BooleanField, DateField, IntegerField)

from antiintuit.basic import truncate, sub_timedelta
from antiintuit.config import Config
from antiintuit.database.exceptions import DatabaseException
from antiintuit.logger import get_logger

__all__ = [
    "BaseModel",
    "Account",
    "DeletedAccount",
    "Course",
    "Subscribe",
    "Test",
    "Question",
    "Answer",
    "create_tables"
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
            return truncate(self.describe, 100)
        else:
            str(super())

    class Meta:
        database = get_system_database()


class Account(BaseModel):
    first_name = CharField()
    last_name = CharField()
    email = CharField()
    password = CharField()
    reserved_until = DateTimeField(default=datetime(1, 1, 1))

    @property
    def describe(self) -> str:
        return "[{}] {} {} <{}>".format(self.id, self.first_name, self.last_name, self.email)

    def reserve(self):
        if self.get_id() is not None:
            self.reserved_until = datetime.utcnow()
            self.save()

    def delete_instance(self, database_only=False, recursive=False, delete_nullable=False):
        Subscribe.delete().where(Subscribe.account == self).execute()
        Test.update({Test.watcher: None}).where(Test.watcher == self).execute()
        DeletedAccount.create_from_account(self, not database_only)
        super().delete_instance(recursive, delete_nullable)


class DeletedAccount(Account):
    is_deleted_on_site = BooleanField()

    @classmethod
    def create_from_account(cls, account: Account, is_deleted_on_site):
        return cls.create(first_name=account.first_name, last_name=account.last_name, email=account.email,
                          password=account.password, reserved_until=account.reserved_until,
                          created_at=account.created_at, is_deleted_on_site=is_deleted_on_site)


class Course(BaseModel):
    publish_id = CharField(unique=True)
    title = CharField()
    published_on = DateField()
    last_scan_at = DateTimeField(default=datetime(1, 1, 1))

    @property
    def publish_id_numbers(self):
        return str(self.publish_id).split("/")

    @property
    def describe(self) -> str:
        return "[{}][{}] {}".format(self.id, self.publish_id, self.title)

    def update_last_scan(self):
        self.last_scan_at = datetime.utcnow()
        self.save()


class Subscribe(BaseModel):
    account = ForeignKeyField(Account, backref="subscriptions")
    course = ForeignKeyField(Course, backref="subscriptions")


class Test(BaseModel):
    publish_id = CharField(unique=True)
    title = CharField()
    last_scan_at = DateTimeField(default=datetime(1, 1, 1))
    course = ForeignKeyField(Course, backref="tests")
    watcher = ForeignKeyField(Account, backref="tests", null=True)
    questions_count = IntegerField()
    passed_count = IntegerField(default=0)
    not_passed_count = IntegerField(default=0)
    average_rating = IntegerField(default=0)
    last_rating = IntegerField(default=0)
    max_rating = IntegerField(default=0)
    unsolvable = BooleanField(default=False)

    @property
    def publish_id_numbers(self):
        split_publish_id = str(self.publish_id).split("/")
        return split_publish_id[:2] + split_publish_id[3:]

    @property
    def describe(self) -> str:
        return "[{}][{}] {}".format(self.id, self.publish_id, self.title)

    @property
    def total_passed(self) -> int:
        return self.passed_count + self.not_passed_count

    def update_last_update(self):
        self.last_scan_at = datetime.utcnow()
        self.save()

    def update_stats(self, passed, grade):
        """Updates the average rating, amount of the passes and the last update time"""
        if self.average_rating > 0:
            self.average_rating = int((self.average_rating * self.total_passed + grade) / (self.total_passed + 1))
        else:
            self.average_rating = grade
        if grade > self.max_rating:
            self.max_rating = grade
        self.last_rating = grade
        if passed:
            self.passed_count += 1
        else:
            self.not_passed_count += 1
        self.update_last_update()
        logger.debug("'%s' test has been updated (average rating: %i, passed tests: %i, not passed tests %i).",
                     str(self), self.average_rating, self.passed_count, self.not_passed_count)

    def set_watcher(self, watcher: Account):
        self.watcher = watcher
        self.save()

    def set_as_unsolvable(self):
        self.unsolvable = True
        self.watcher = None
        self.save()


class VariantsModelInterface(BaseModel):
    """Interface for a question and an answer classes"""
    _variants = TextField(help_text="The field contains a dict of variants in JSON as handled text")

    @property
    def variants(self) -> list:
        """Returns variants as list of handled text variants"""
        return json.loads(self._variants)

    @variants.setter
    def variants(self, variants: list):
        """Writes variants from list of handled text variants"""
        self._variants = json.dumps(variants)


class Question(VariantsModelInterface):
    task_id = IntegerField(unique=True)
    title = TextField()
    last_update_at = DateTimeField(default=datetime(1, 1, 1))
    type = CharField()
    course = ForeignKeyField(Course, backref="questions")
    locked_by = CharField(null=True, default=None)
    locked_at = DateTimeField(default=None, null=True)
    original_html = TextField(default=None)

    @staticmethod
    def unlock_all_session_question():
        return (Question
                .update({Question.locked_by: None, Question.locked_at: None})
                .where(Question.locked_by == Config.SESSION_ID)
                ).execute()

    @property
    def describe(self) -> str:
        return "[{}][{}][{}] {}".format(self.id, self.task_id, self.type, self.title)

    @property
    def is_right_answer_exists(self) -> bool:
        return Answer.select().where((Answer.question == self) & (Answer.status == "R")).count() == 1

    @property
    def unchanged_answers_count(self) -> int:
        return Answer.select().where((Answer.question == self) & (Answer.status == "U")).count()

    def lock(self):
        self2 = Question.get_by_id(self.id)
        if self2.locked_by is None:
            self.locked_by = Config.SESSION_ID
            self.locked_at = datetime.utcnow()
            self.save()
            logger.debug("Question '%s' has been locked by '%s'.", str(self), self.locked_by)
            return True
        return False

    def unlock(self):
        if self.locked_by == Config.SESSION_ID:
            self.locked_by = None
            self.locked_at = None
            self.save()
            logger.debug("Question '%s' has been unlocked.", str(self))
            return True
        return False

    @staticmethod
    def unlock_all_questions(age_minutes: int = None):
        if age_minutes is None:
            unlocked = Question.update({Question.locked_by: None, Question.locked_at: None}).execute()
            logger.info("%i old questions have been unlocked", unlocked)
        else:
            age_moment = sub_timedelta(timedelta(minutes=age_minutes))
            unlocked = (Question
                        .update({Question.locked_by: None, Question.locked_at: None})
                        .where(Question.locked_at < age_moment)).execute()
            logger.info("%i old questions (max age: %i) have been unlocked", unlocked, age_minutes)

    def delete_answers(self):
        logger.debug("The answers of '%s' question will be deleted.", str(self))
        return Answer.delete().where(Answer.question == self).execute()

    def delete_instance(self, recursive=False, delete_nullable=False):
        self.delete_answers()
        super().delete_instance(recursive, delete_nullable)
        logger.debug("'%s' question has been deleted.", str(self))

    def get_next_answer(self):
        """Returns the first right or unchecked answer of the question"""
        try:
            return (Answer
                    .select()
                    .where(Answer.question == self)
                    .order_by(Answer.status).limit(1)).get()
        except Answer.DoesNotExist:
            return None


class Answer(VariantsModelInterface):
    status = CharField(max_length=1, default="U",
                       help_text="The field contains a status of the answer. Can be Right(R), Wrong(W) or Unchecked(U)")
    question = ForeignKeyField(Question, backref="answers")

    @property
    def describe(self) -> str:
        return "[{}] {}".format(self.id, ", ".join(map(lambda v: str(v[-1]), self.variants)))

    def set_as(self, status: str):
        if status in ("U", "R", "W"):
            self.status = status
            self.save()
            logger.debug("The status of '%s' answer set up as '%s'.", str(self), self.status)

    def set_as_right(self):
        self.set_as("R")

    def set_as_wrong(self):
        if self.status == "R":
            question = self.question
            logger.warning("The '%s' answer of the '%s' question in the '%s' course had 'R' status, "
                           "but it will be changed to 'W'.", str(self), str(question), str(question.course))
        self.set_as("W")


def create_tables():
    for model in Account, DeletedAccount, Course, Test, Question, Answer, Subscribe:
        if not model.table_exists():
            model.create_table()
            logger.info("Model '%s' has been created.", model.__name__)
