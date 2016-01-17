#!/usr/bin/env python
import os
from setuptools import setup, find_packages


packages_list = ['xmljson', 'numpy>=1.10.1', 'scipy>=0.16.0', 'GDAL',
                 'numexpr>=2.4.0', 'dask[array]', 'dask[bag]', 'toolz']
templates_list_files = os.listdir('./execution_templates_devel')
templates_list_files = [os.path.join('./execution_templates_devel', f) for f in templates_list_files]
conf_list_files = os.listdir('./configuration')
conf_list_files = [os.path.join('./configuration', f) for f in conf_list_files if f.endswith('json')]

setup(name='pyg2p',
      version='2.0.1',
      description="Convert GRIB files to PCRaster",
      license="Commercial",
      install_requires=packages_list,
      author="Domenico Nappo",
      author_email="domenico.nappo@gmail.com",
      packages=find_packages(),
      keywords="GRIB PCRaster pyg2p",
      entry_points={'console_scripts': ['pyg2p = pyg2p.scripts.pyg2p_script:main_script']},
      data_files=[('configuration', conf_list_files),
                  ('configuration/geopotentials', ['configuration/geopotentials/readme.txt']),
                  ('configuration/tests', ['configuration/tests/commands.txt']),
                  ('configuration/intertables', ['configuration/intertables/readme.txt']),
                  ('docs', ['./Docs/UserManual.pdf']),
                  ('execution_templates_examples', templates_list_files)],
      zip_safe=True)

