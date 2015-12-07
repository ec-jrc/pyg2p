from sys import stdout


def progress_step_and_backchar(num_cells):
    progress_step = num_cells / 100
    back_char = '\r'
    if not stdout.isatty():
        # out is being redirected
        back_char = '\n'
    return back_char, progress_step

__all__ = ['Interpolation', 'LatLongDem']