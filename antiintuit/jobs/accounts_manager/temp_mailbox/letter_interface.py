__all__ = [
    "LetterInterface"
]


class LetterInterface:
    """Realization of a mail for working with mails from another services"""

    def __init__(self, recipient, sender_address, sender_name, subject, text):
        self.is_read = False
        self._recipient, self._sender_address = recipient, sender_address
        self._subject, self._text, self._sender_name = subject, text, sender_name

    @property
    def sender_address(self) -> str:
        """Sender's email address"""
        return self._sender_address

    @property
    def sender_name(self) -> str:
        """Sender's name"""
        return self._sender_name

    @property
    def recipient(self) -> str:
        """recipient's email address"""
        return self._recipient

    @property
    def subject(self) -> str:
        """A subject of the letter"""
        return self._subject

    @property
    def text(self) -> str:
        """Text of the letter"""
        return self._text
