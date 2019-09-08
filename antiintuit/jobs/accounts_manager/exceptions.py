from antiintuit.exceptions import AntiintuitException

__all__ = [
    "AccountManagerException",
    "OperationHasDoneUnsuccessfully",
    "ReceivedDataIsNotFull",
    "RegistrationError",
    "AuthorizationError"
]


class AccountManagerException(AntiintuitException):
    pass


class OperationHasDoneUnsuccessfully(AccountManagerException):
    pass


class ReceivedDataIsNotFull(AccountManagerException):
    pass


class RegistrationError(AccountManagerException):
    pass


class AuthorizationError(AccountManagerException):
    pass
