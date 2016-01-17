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
      entry_points={'console_scripts': ['pyg2p = pyg2p.pyg2p:main']},
      zip_safe=True)

