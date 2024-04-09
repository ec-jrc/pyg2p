import os
import subprocess
import sys
import glob
from shutil import rmtree
from setuptools import setup, find_packages, Command

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, './src/'))

version_file = os.path.join(current_dir, 'src/pyg2p/VERSION')

with open(version_file, 'r') as f:
    version = f.read().strip()

readme_file = os.path.join(current_dir, 'README.md')
with open(readme_file, 'r') as f:
    long_description = f.read()

"""
---------------------------------------------------------------------------------------------------------------------------------------
To publish a new version of this distribution (git tags and pypi package), after pushed on main branch:

python setup.py testpypi
python setup.py publish

Test package install
pip install --index-url https://test.pypi.org/simple/ pyg2p==3.2.1
"""

class UploadCommand(Command):
    """Support setup.py upload."""

    description = 'Publish pyg2p package.'
    user_options = []

    @staticmethod
    def print_console(s):
        print(f'\033[1m{s}\033[0m')

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
        os.system(f'{sys.executable} setup.py sdist')

        self.print_console('Uploading the package to PyPI via Twine...')
        os.system('twine upload dist/*')

        self.print_console('Pushing git tags...')
        os.system('git tag v{}'.format(version))
        os.system('git push --tags')

        sys.exit()

class UploadCommandTest(UploadCommand):

    def run(self):
        try:
            self.print_console('Removing previous builds...')
            rmtree(os.path.join(current_dir, 'dist'))
        except OSError:
            pass

        self.print_console('Building Source and Wheel (universal) distribution...')
        os.system('{} setup.py sdist'.format(sys.executable))

        self.print_console('Uploading the package to test PyPI via Twine...')
        os.system('twine upload --repository testpypi dist/*')

        sys.exit()

def delete_files_from_dir(dir_path, prefix_=''):
    # Gather directory contents
    if is_dir(dir_path):
        contents = [os.path.join(dir_path, i) for i in os.listdir(dir_path)]
        # Iterate and remove each item in the appropriate manner
        [os.unlink(i) for i in contents if i.startswith(prefix_)]

def create_dir(pathname, recreate=False):
    if not os.path.exists(pathname):
        os.makedirs(pathname)
    elif recreate:
        delete_files_from_dir(pathname)
        os.rmdir(pathname)
        os.makedirs(pathname)

def is_dir(pathname):
    return os.path.isdir(pathname) and pathname not in ('.', '..', './', '../')

def exists(pathname, is_folder=False):
    return os.path.exists(pathname) and (os.path.isdir(pathname) if is_folder else os.path.isfile(pathname))

def filename(pathname):
    return os.path.basename(pathname)

def setup_data_files(setup_args_):
    user_conf_dir = f'{os.path.expanduser("~")}/.pyg2p/'
    create_dir(user_conf_dir)
    list_files = {t: [os.path.join(t, f) for f in os.listdir(t) if f.endswith('.json')]
                  for t in ('./templates',
                            './configuration',
                            './configuration/global')}
    for_user_to_copy = [f for f in list_files['./configuration'] if
                        not exists(os.path.join(user_conf_dir, filename(f)))]
    templates_to_copy = [f for f in list_files['./templates'] if
                         not exists(os.path.join(user_conf_dir, 'templates_samples', filename(f)))]
    data_files = [('pyg2p/configuration/', list_files['./configuration/global'])]

    if for_user_to_copy:
        data_files.append((user_conf_dir, for_user_to_copy))
    if templates_to_copy:
        data_files.append((os.path.join(user_conf_dir, 'templates_samples'), templates_to_copy))
    setup_args_.update({'data_files': data_files})


def _get_gdal_version():
    try:
        p = subprocess.Popen(['gdal-config', '--version'], stdout=subprocess.PIPE)
    except FileNotFoundError:
        raise SystemError('gdal-config not found.'
                          'GDAL seems not installed. '
                          'Please, install GDAL binaries and libraries for your system '
                          'and then install the relative pip package.')
    else:
        return p.communicate()[0].splitlines()[0].decode()


gdal_version = _get_gdal_version()
req_file = 'requirements.txt'
requirements = [l for l in open(req_file).readlines() if l and not l.startswith('#')]
requirements += [f'GDAL=={gdal_version}']

setup_args = dict(name='pyg2p',
                  version=version,
                  description="Convert GRIB files to netCDF or PCRaster",
                  long_description=long_description,
                  long_description_content_type='text/markdown',
                  license="EUPL 1.2",
                  install_requires=requirements,
                  author="Domenico Nappo",
                  author_email="domenico.nappo@gmail.com",
                  package_dir={'': 'src/'},
                  py_modules=[os.path.splitext(os.path.basename(path))[0] for path in glob.glob('src/*.py*')],
                  include_package_data=True,
                  package_data={'pyg2p': ['*.json', 'VERSION']},
                  packages=find_packages('src'),
                  keywords="NetCDF GRIB PCRaster Lisflood EFAS GLOFAS",
                  scripts=['bin/pyg2p'],
                  zip_safe=False,
                  # setup.py publish to pypi.
                  cmdclass={
                     'upload': UploadCommand,
                     'publish': UploadCommand,
                     'testpypi': UploadCommandTest,
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
