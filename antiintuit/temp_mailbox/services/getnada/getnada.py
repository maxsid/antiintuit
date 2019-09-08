from random import randint

from requests import Session

from antiintuit.logger import get_logger
from antiintuit.temp_mailbox.letter_interface import LetterInterface
from antiintuit.temp_mailbox.mailbox_interface import MailboxInterface

__all__ = [
    "GetnadaMailbox",
    "GetnadaLetter"
]

logger = get_logger("antiintuit", "temp_mailbox", "getnada")


class GetnadaMailbox(MailboxInterface):
    def __init__(self):
        self._session = Session()
        super().__init__(self._get_new_email())
        logger.info("Getnada mailbox {} has been initialized".format(self.email))
        self.refresh()

    def _request(self, *commands, method="GET", **kwargs) -> dict:
        command = "/".join(["https://getnada.com/api/v1", *map(str, commands)])
        resp = self._session.request(method, command, **kwargs)
        resp = resp.json()
        return resp

    def _get_domains(self):
        return list(map(lambda d: d["name"], self._request("domains")))

    def _get_new_email(self) -> str:
        domains = self._get_domains()
        login = "".join([chr(randint(97, 122)) for _ in range(randint(7, 15))])
        domain_position = randint(0, len(domains) - 1)
        return "{}@{}".format(login, domains[domain_position])

    def refresh(self) -> iter:
        msgs = self._request("inboxes", self.email)["msgs"]
        for uid in map(lambda m: m["uid"], msgs):
            message_data = self._request("messages", uid)
            self._messages.append(GetnadaLetter(
                recipient=self.email,
                sender_address=message_data["fe"],
                sender_name=message_data["f"],
                subject=message_data["s"],
                text=message_data["html"]
            ))
            self._request("messages", uid, method="DELETE")
        logger.debug("The messages has been updated. They is {} now (new is {})"
                     .format(len(self.messages), len(self.new_messages)))

    def __del__(self):
        pass


class GetnadaLetter(LetterInterface):
    pass
