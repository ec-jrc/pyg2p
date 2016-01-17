#!/usr/bin/env python
from setuptools import setup, find_packages
from distutils.command.install import install as _install


# class Install(_install):
#
#     def _post_install(self):
#
#         import test_reqs
#         test_reqs.test_reqs()
#
#     def run(self):
#         _install.run(self)
#         self._post_install()


packages_list = ['xmljson', 'numpy>=1.10.1', 'scipy>=0.16.0', 'GDAL',
                 'numexpr>=2.4.0', 'dask[array]', 'dask[bag]', 'toolz']
setup(name='pyg2p',
      version='2.0',
      description="Convert GRIB files to PCRaster",
      license="Commercial",
      install_requires=packages_list,
      author="Domenico Nappo",
      author_email="domenico.nappo@gmail.com",
      packages=find_packages(),
      keywords="GRIB PCRaster pyg2p",
      # cmdclass={'install': Install},
      entry_points={'console_scripts': ['pyg2p = scripts.pyg2p:main']},
      data_files=[('configuration', ['configuration/test.json', 'configuration/parameters.json',
                                     'configuration/geopotentials.json', 'configuration/intertables.json']),
                  ('configuration/geopotentials', ['configuration/geopotentials/readme.txt']),
                  ('configuration/tests', ['configuration/tests/commands.txt']),
                  ('configuration/intertables', ['configuration/intertables/readme.txt']),
                  ('docs', ['./Docs/UserManual.pdf']),
                  ('execution_templates_examples', ['./execution_templates_devel/'])],
      # package_dir={'pyg2p': './'},
      # package_data={'pyg2p': ['configuration/*', 'Docs/*', 'execution_templates_devel']},
      zip_safe=True)

