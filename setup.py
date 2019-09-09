import os
import sys
import glob
from setuptools import setup, find_packages

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, './src/'))

import pyg2p.util.files as fm
from pyg2p import __version__

readme_file = os.path.join(current_dir, 'README.md')
with open(readme_file, 'r') as f:
    long_description = f.read()


def setup_data_files(setup_args_):
    user_conf_dir = '{}/{}'.format(os.path.expanduser('~'), '.pyg2p/')
    fm.create_dir(user_conf_dir)
    list_files = {t: [os.path.join(t, f) for f in os.listdir(t) if f.endswith('.json')]
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


packages_deps = ['ujson', 'xmljson', 'numpy', 'scipy', 'eccodes-python',
                 'numexpr', 'dask[bag]', 'dask[array]', 'toolz']

setup_args = dict(name='pyg2p',
                  version=__version__,
                  description="Convert GRIB files to PCRaster",
                  long_description=long_description,
                  license="Commercial",
                  install_requires=packages_deps,
                  author="Domenico Nappo",
                  author_email="domenico.nappo@gmail.com",
                  package_dir={'': 'src/'},
                  py_modules=[os.path.splitext(os.path.basename(path))[0] for path in glob.glob('src/*.py*')],
                  include_package_data=True,
                  package_data={'pyg2p': ['*.xml']},
                  packages=find_packages('src'),
                  keywords="NetCDF GRIB PCRaster pyg2p",
                  scripts=['bin/pyg2p'],
                  # entry_points={'console_scripts': ['pyg2p = pyg2p.scripts.pyg2p_script:main_script']},
                  zip_safe=True,
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
