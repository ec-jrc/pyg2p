import os
import sys
import logging

from lisfloodutilities.compare import PCRComparator

current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(current_dir, '../src/')
print(src_path)
sys.path.append(src_path)

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)
logger = logging.getLogger()
logger.propagate = False


def check_dataset(self, ds):
    result_dir = self.options['results'].joinpath(f'{ds}')
    reference_dir = self.options['reference'].joinpath(f'{ds}')
    comparator = PCRComparator()
    diffs = comparator.compare_dirs(reference_dir.as_posix(), result_dir.as_posix(), skip_missing=False)
    if diffs:
        logger.info(diffs)
    assert not diffs
