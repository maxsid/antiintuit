from antiintuit.exceptions import AntiintuitException

__all__ = [
    "ConfigReaderException",
    "ConfigDirectoryIsNotExist"
]


class ConfigReaderException(AntiintuitException):
    pass


class ConfigDirectoryIsNotExist(ConfigReaderException):
    pass
