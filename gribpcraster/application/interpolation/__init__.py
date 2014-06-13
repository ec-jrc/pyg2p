from sys import stdout

__author__ = "domenico nappo"
__date__ = "$June 13, 2014 12:19 AM$"


def progress_step_and_backchar(num_cells):
    progress_step = num_cells / 1000
    back_char = '\r'
    if not stdout.isatty():
        # out is being redirected
        progress_step = num_cells / 100
        back_char = '\n'
    return back_char, progress_step

__all__ = ['Interpolation', 'LatLongDem']