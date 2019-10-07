from random import shuffle

from antiintuit.jobs.accounts_manager.temp_mailbox.mailbox_interface import MailboxInterface
from antiintuit.jobs.accounts_manager.temp_mailbox.services.getnada import GetnadaMailbox
from antiintuit.jobs.accounts_manager.temp_mailbox.services.mytemp_email import MyTempEmailMailbox

__all__ = [
    "get_random_mailbox"
]


def get_random_mailbox():
    """Returns randomly one of some services"""
    mailboxes = [
        GetnadaMailbox,
        MyTempEmailMailbox
    ]
    while True:
        shuffle(mailboxes)
        for mailbox in mailboxes:
            m: MailboxInterface = mailbox()
            yield m
