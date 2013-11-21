__author__ = 'dominik'

FALSE_STRINGS = ['FALSE', 'F', 'False', 'false', 'NO', 'no', 'No', '0']

def is_stringlike(a):
        if type(a) == str or type(a) == bytes or type(a) == unicode:
            return True
        else:
            return False

def is_container(a):
    try:
        1 in a
    except:
        return False
    if is_stringlike(a):
        return False
    return True


def is_callable(v):
    return hasattr(v, '__call__')