import re

__all__ = [
    "get_number",
    "message_is_digit",
    "message_is_not_digit"
]

main_commands = [
    "/course"
]


def get_number(command: str, decrement=1):
    match = re.search(r"/?(\d+)\.?", command)
    if match is None:
        return None
    return int(match.group(1)) - decrement


def message_is_digit(message, is_digit=True, not_contains=None):
    not_contains = not_contains or main_commands
    text = message.text
    if is_digit:
        return (text.isdigit() or text[1:].isdigit()) and text not in not_contains
    else:
        return not (text.isdigit() or text[1:].isdigit()) and text not in not_contains


def message_is_not_digit(message, not_contains=None):
    return message_is_digit(message, False, not_contains)
