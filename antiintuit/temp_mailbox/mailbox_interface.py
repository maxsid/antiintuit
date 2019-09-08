__all__ = [
    "MailboxInterface"
]


class MailboxInterface:
    def __init__(self, email=None):
        self._email = email
        self._messages = list()

    @property
    def email(self) -> str:
        """The property returns string with a email-address of the current mailbox"""
        return self._email

    @property
    def messages(self) -> list:
        """The property returns a list with all messages of the current mailbox"""
        return self._messages

    @property
    def new_messages(self) -> list:
        """Return a list with unread messages of the current mailbox"""
        new_messages = filter(lambda m: not m.is_read, self.messages)
        return list(new_messages)

    def __del__(self):
        """This magic method should provide deleting the current mailbox"""
        raise NotImplementedError("__del__ isn't overloaded.")

    def refresh(self) -> iter:
        """The method updates messages from servers"""
        raise NotImplementedError("refresh function isn't overloaded.")

    def mark_all_messages_as_read(self):
        """The method changes 'is_read', inside new messages, to 'True'."""
        for message in self.new_messages:
            message.is_read = True
