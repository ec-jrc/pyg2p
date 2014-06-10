import csv
import util.date.Dates as Dates
"""Module for conversion operations from a String """


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
    return filter(_is_empty_string, list(c)[0])

def to_argdict(string_):
    c = csv.reader(csv.StringIO(string_), delimiter=" ")
    l = filter(_is_empty_string, list(c)[0])
    d = {}
    for i in range(0, len(l), 2):
        d[l[i]] = l[i + 1]
    return d