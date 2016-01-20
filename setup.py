#!/usr/bin/env python
import os
from setuptools import setup, find_packages
import pyg2p.util.files as fm

packages_list = ['xmljson', 'numpy>=1.10.1', 'scipy>=0.16.0', 'GDAL>=1.9.0',
                 'numexpr>=2.4.6', 'dask[bag]', 'dask[array]', 'toolz']
templates_list_files = [os.path.join('./execution_templates_devel', f) for f in os.listdir('./execution_templates_devel') if f.endswith('json')]
conf_list_files = [os.path.join('./configuration', f) for f in os.listdir('./configuration') if f.endswith('json')]
global_conf_list_files = [os.path.join('./configuration/global', f) for f in os.listdir('./configuration/global') if f.endswith('json')]
user_conf_dir = '{}/{}'.format(os.path.expanduser('~'), '.pyg2p/')
fm.create_dir(user_conf_dir)
setup_args = dict(name='pyg2p',
                  version='2.0.0',
                  description="Convert GRIB files to PCRaster",
                  license="Commercial",
                  install_requires=packages_list,
                  author="Domenico Nappo",
                  author_email="domenico.nappo@gmail.com",
                  packages=find_packages(),
                  keywords="GRIB PCRaster pyg2p",
                  entry_points={'console_scripts': ['pyg2p = pyg2p.scripts.pyg2p_script:main_script']},
                  zip_safe=True)

data_files = [('pyg2p/configuration/', global_conf_list_files)]
for_user_to_copy = [f for f in conf_list_files if not fm.exists(os.path.join(user_conf_dir, fm.filename(f)))]
if for_user_to_copy:
    data_files.append((user_conf_dir, for_user_to_copy))

templates_to_copy = [f for f in templates_list_files if not fm.exists(os.path.join(user_conf_dir, 'templates_samples', fm.filename(f)))]
if templates_to_copy:
    data_files.append((os.path.join(user_conf_dir, 'templates_samples'), templates_to_copy))

if not fm.exists(os.path.join(user_conf_dir, 'tests/commands.txt')):
    data_files.append((os.path.join(user_conf_dir, 'tests'), ['configuration/tests/commands.txt']))

data_files.append((os.path.join(user_conf_dir, 'docs'), ['./Docs/UserManual.pdf']))

setup_args.update({'data_files': data_files})

setup(**setup_args)

