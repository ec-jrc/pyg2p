import csv
import re
from datetime import datetime


def to_boolean(bool_):
    """
    Convert to boolean from String

    Return: a boolean value

    If the string is not a representation of a boolean value, the method returns False.
    """
    if bool_ is None:
        return False
    if bool_ is True or bool_ is False:
        return bool_
    else:
        return bool_[0].upper() == 'T' or bool_[0].upper() == 'Y'


def _is_empty_string(string_):
    return string_ is not ''


def to_argv(string_):
    c = csv.reader(csv.StringIO(string_), delimiter=" ")
    return list(filter(_is_empty_string, list(c)[0]))


def to_argdict(string_):
    c = re.split(' |=', string_.strip(), maxsplit=0)
    return dict(zip(c[0::2], c[1::2]))


FALSE_STRINGS = ['FALSE', 'F', 'f', 'False', 'false', 'NO', 'no', 'No', '0']


def now_string(fmt='%Y-%m-%d %H:%M'):
    # noinspection PyTypeChecker
    return datetime.strftime(datetime.now(), fmt)
