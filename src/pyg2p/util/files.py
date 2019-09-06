import re
import shutil as sh
import os
from functools import partial


def ls(path, extension=None):
    join = partial(os.path.join, path)
    if not extension:
        return [join(f) for f in os.listdir(path) if not is_dir(f)]
    return [join(f) for f in os.listdir(path) if not is_dir(f) and f.endswith(extension)]


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
    return os.path.exists(pathname) and (os.path.isdir(pathname) if is_folder else os.path.isfile(pathname))


def is_xml(pathname):
    return os.path.isfile(pathname) and pathname.endswith('.xml')


def is_conf(pathname):
    return os.path.isfile(pathname) and pathname.endswith('.conf')


def is_dir(pathname):
    return os.path.isdir(pathname) and pathname not in ('.', '..', './', '../')


def has_perms(pathnames, perm):
    if not isinstance(pathnames, (tuple, list)):
        pathnames = [pathnames]
    for path in pathnames:
        if path and not os.access(path, perm):
            return False
    return True


def can_write(pathnames):
    return has_perms(pathnames, os.W_OK)


def can_read(pathnames):
    return has_perms(pathnames, os.R_OK)


def create_dir(pathname, recreate=False):
    if not os.path.exists(pathname):
        os.makedirs(pathname)
    elif recreate:
        delete_files_from_dir(pathname)
        os.rmdir(pathname)
        os.makedirs(pathname)


def filename(pathname):
    return os.path.basename(pathname)


def dir_filename(pathname):
    return os.path.dirname(pathname), os.path.basename(pathname)


def without_ext(filepath):
    return os.path.splitext(filepath)[0]


def ext(filepath):
    return os.path.splitext(filepath)[1]


def copy(file_, to_dir, backup=False):
    if backup and exists(os.path.join(to_dir, filename(file_))):
        to_dir = os.path.join(to_dir, filename(file_) + '.backup')
    sh.copy(file_, to_dir)


def copy_dir(source_dir, target_dir, recreate=False):
    create_dir(target_dir, recreate=recreate)
    if is_dir(source_dir):
        contents = [os.path.join(source_dir, i) for i in os.listdir(source_dir)]
        [copy(f, target_dir) for f in contents]


def normalize_filename(name):

    normalized_name = without_ext(name).lower()
    # remove long numbers (like dates 20151225)
    normalized_name = re.sub(r'([0-9]{8,10})', '', normalized_name) or normalized_name
    # remove ., - and _
    normalized_name = normalized_name.replace('-', '').replace('_', '').replace('.', '')
    # remove extension

    if len(normalized_name) < 3:
        return name.replace('.', '_')
    # return only first 10 chars
    return normalized_name[:10]
