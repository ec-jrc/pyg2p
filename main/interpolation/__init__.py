from sys import stdout


def progress_step_and_backchar(num_cells):
    progress_step = num_cells / 1000
    back_char = '\r'
    if not stdout.isatty():
        # out is being redirected
        back_char = '\n'
        progress_step *= 10
    return back_char, progress_step

__all__ = ['Interpolation', 'LatLongDem']