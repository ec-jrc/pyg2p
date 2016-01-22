#!/usr/bin/env python
import os
from setuptools import setup, find_packages
import pyg2p.util.files as fm


def setup_data_files(setup_args_):
    user_conf_dir = '{}/{}'.format(os.path.expanduser('~'), '.pyg2p/')
    fm.create_dir(user_conf_dir)
    list_files = {t: [os.path.join(t, f) for f in os.listdir(t) if f.endswith('json')]
                  for t in ('./execution_templates_devel',
                            './configuration',
                            './configuration/global')}
    for_user_to_copy = [f for f in list_files['./configuration'] if
                        not fm.exists(os.path.join(user_conf_dir, fm.filename(f)))]
    templates_to_copy = [f for f in list_files['./execution_templates_devel'] if
                         not fm.exists(os.path.join(user_conf_dir, 'templates_samples', fm.filename(f)))]
    data_files = [('pyg2p/configuration/', list_files['./configuration/global'])]
    if for_user_to_copy:
        data_files.append((user_conf_dir, for_user_to_copy))
    if templates_to_copy:
        data_files.append((os.path.join(user_conf_dir, 'templates_samples'), templates_to_copy))
    if not fm.exists(os.path.join(user_conf_dir, 'tests/commands.txt')):
        data_files.append((os.path.join(user_conf_dir, 'tests'), ['configuration/tests/commands.txt']))
    data_files.append((os.path.join(user_conf_dir, 'docs'), ['./Docs/UserManual.pdf']))
    setup_args_.update({'data_files': data_files})

packages_deps = ['xmljson', 'numpy>=1.10.1', 'scipy>=0.16.0', 'GDAL>=1.9.0',
                 'numexpr>=2.4.6', 'dask[bag]', 'dask[array]', 'toolz']

setup_args = dict(name='pyg2p',
                  version='2.0.0',
                  description="Convert GRIB files to PCRaster",
                  license="Commercial",
                  install_requires=packages_deps,
                  author="Domenico Nappo",
                  author_email="domenico.nappo@gmail.com",
                  packages=find_packages(),
                  keywords="GRIB PCRaster pyg2p",
                  entry_points={'console_scripts': ['pyg2p = pyg2p.scripts.pyg2p_script:main_script']},
                  zip_safe=True)

setup_data_files(setup_args)

setup(**setup_args)

