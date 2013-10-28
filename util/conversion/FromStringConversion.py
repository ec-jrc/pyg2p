import csv
import util.date.Dates as Dates
__docformat__ = 'restructuredtext'
"""Module for conversion operations from a String """

    
def toBoolean(bool):
    """
    Convert to boolean from String

    Return: a boolean value

    If the string is not a representation of a boolean value, the method returns False.
    """
    if bool is None:
        return False
    if bool is True or bool is False:
        return bool
    else:
        return bool[0].upper() == 'T' or bool[0].upper() == 'Y'

def toDate(dateString,fmt):
    return Dates.datetimeFromString(dateString, fmt)

def nvl(string, alternative=' - '):
    if string==None:
        return alternative
    else:
        return string

def is_empty_string(string_):
    return string_ is not ''

def to_argv(string_):
    s = csv.StringIO(string_)
    c = csv.reader(s, delimiter=" ")
    return filter(is_empty_string, list(c)[0])