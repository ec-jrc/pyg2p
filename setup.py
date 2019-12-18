import os
import sys
import glob
from shutil import rmtree
from setuptools import setup, find_packages, Command

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, './src/'))

import pyg2p.util.files as fm
from pyg2p import __version__

readme_file = os.path.join(current_dir, 'README.md')
with open(readme_file, 'r') as f:
    long_description = f.read()


class UploadCommand(Command):
    """Support setup.py upload."""

    description = 'Publish pyg2p package.'
    user_options = []

    @staticmethod
    def print_console(s):
        print('\033[1m{0}\033[0m'.format(s))

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        try:
            self.print_console('Removing previous builds...')
            rmtree(os.path.join(current_dir, 'dist'))
        except OSError:
            pass

        self.print_console('Building Source and Wheel (universal) distribution...')
        os.system('{0} setup.py sdist'.format(sys.executable))

        self.print_console('Uploading the package to PyPI via Twine...')
        os.system('twine upload dist/*')

        self.print_console('Pushing git tags...')
        os.system('git tag {0}'.format(__version__))
        os.system('git push --tags')

        sys.exit()



def setup_data_files(setup_args_):
    user_conf_dir = '{}/{}'.format(os.path.expanduser('~'), '.pyg2p/')
    fm.create_dir(user_conf_dir)
    list_files = {t: [os.path.join(t, f) for f in os.listdir(t) if f.endswith('.json')]
                  for t in ('./templates',
                            './configuration',
                            './configuration/global')}
    for_user_to_copy = [f for f in list_files['./configuration'] if
                        not fm.exists(os.path.join(user_conf_dir, fm.filename(f)))]
    templates_to_copy = [f for f in list_files['./templates'] if
                         not fm.exists(os.path.join(user_conf_dir, 'templates_samples', fm.filename(f)))]
    data_files = [('pyg2p/configuration/', list_files['./configuration/global'])]

    if for_user_to_copy:
        data_files.append((user_conf_dir, for_user_to_copy))
    if templates_to_copy:
        data_files.append((os.path.join(user_conf_dir, 'templates_samples'), templates_to_copy))
    if not fm.exists(os.path.join(user_conf_dir, 'tests/commands.txt')):
        data_files.append((os.path.join(user_conf_dir, 'tests'), ['configuration/tests/commands.txt']))
    setup_args_.update({'data_files': data_files})


packages_deps = ['ujson',
                 'numpy>=1.16.0', 'scipy>=0.16', 'numexpr>=2.4.6', 'netCDF4',
                 # 'eccodes-python',
                 'dask[bag]', 'dask[array]', 'toolz']

setup_args = dict(name='pyg2p',
                  version=__version__,
                  description="Convert GRIB files to netCDF or PCRaster",
                  long_description=long_description,
                  long_description_content_type='text/markdown',
                  license="EUPL 1.2",
                  install_requires=packages_deps,
                  author="Domenico Nappo",
                  author_email="domenico.nappo@gmail.com",
                  package_dir={'': 'src/'},
                  py_modules=[os.path.splitext(os.path.basename(path))[0] for path in glob.glob('src/*.py*')],
                  include_package_data=True,
                  package_data={'pyg2p': ['*.json']},
                  packages=find_packages('src'),
                  keywords="NetCDF GRIB PCRaster Lisflood EFAS GLOFAS",
                  scripts=['bin/pyg2p'],
                  zip_safe=True,
                  # setup.py publish to pypi.
                  cmdclass={
                     'upload': UploadCommand,
                     'publish': UploadCommand,
                  },
                  classifiers=[
                      # complete classifier list: http://pypi.python.org/pypi?%3Aaction=list_classifiers
                      'Development Status :: 4 - Beta',
                      'Intended Audience :: Developers',
                      'Intended Audience :: Education',
                      'Intended Audience :: Financial and Insurance Industry',
                      'Intended Audience :: Other Audience',
                      'Intended Audience :: Science/Research',
                      'License :: OSI Approved :: European Union Public Licence 1.2 (EUPL 1.2)',
                      'Operating System :: Unix',
                      'Operating System :: POSIX',
                      'Operating System :: Microsoft :: Windows',
                      'Operating System :: MacOS :: MacOS X',
                      'Programming Language :: Python',
                      'Programming Language :: Python :: 3',
                      'Topic :: Scientific/Engineering :: Physics',
                  ])

setup_data_files(setup_args)

setup(**setup_args)
