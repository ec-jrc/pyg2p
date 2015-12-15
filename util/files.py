import os
import shutil as sh
from os import path as path


def delete_file(param):
    if exists(param):
        os.unlink(param)


def delete_files_from_dir(dir_path, prefix_=''):
    # Gather directory contents
    if is_dir(dir_path):
        contents = [os.path.join(dir_path, i) for i in os.listdir(dir_path)]
        # Iterate and remove each item in the appropriate manner
        [os.unlink(i) for i in contents if i.startswith(prefix_)]


def exists(pathname, is_folder=False):
    return path.exists(pathname) and (path.isdir(pathname) if is_folder else path.isfile(pathname))


def is_xml(pathname):
    return path.isfile(pathname) and pathname.endswith('.xml')


def is_conf(pathname):
    return path.isfile(pathname) and pathname.endswith('.conf')


def is_dir(pathname):
    return path.isdir(pathname) and path not in ('.', '..', './', '../')


def create_dir(pathname, recreate=False):
    if not path.exists(pathname):
        os.makedirs(pathname)
    elif recreate:
        delete_files_from_dir(pathname)
        os.rmdir(pathname)
        os.makedirs(pathname)


def file_name(pathname):
    return path.basename(pathname)


def copy(file_, to_dir):
    sh.copy(file_, to_dir)


def copy_dir(source_dir, target_dir, recreate=False):
    create_dir(target_dir, recreate=recreate)
    if is_dir(source_dir):
        contents = [os.path.join(source_dir, i) for i in os.listdir(source_dir)]
        [copy(f, target_dir) for f in contents]
