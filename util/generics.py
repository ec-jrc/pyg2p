from datetime import datetime
from sys import stdout

FALSE_STRINGS = ['FALSE', 'F', 'f', 'False', 'false', 'NO', 'no', 'No', '0']
ENDC = '\033[0m'
BOLD = '\033[1m'
GREEN = '\033[92m' + BOLD
YELLOW = '\033[93m' + BOLD
WARN = '\033[94m' + BOLD
FAIL = '\033[91m' + BOLD
DEFAULT = BOLD


def now_string(fmt='%Y-%m-%d %H:%M'):
    return datetime.strftime(datetime.now(), fmt)


def is_container(a):
    if isinstance(a, (list, tuple, dict)):
        return True
    return False


def is_callable(v):
    return hasattr(v, '__call__')


def progress_step_and_backchar(num_cells):
    progress_step = num_cells / 250
    back_char = '\r'
    if not stdout.isatty():
        # out is being redirected
        back_char = '\n'
        progress_step *= 10
    return back_char, progress_step
