import codecs
import os
import re
import setuptools
import sys

ANCHOR_PATTERN = re.compile('^\.\. _([^:]+):$')

here = os.path.abspath(os.path.dirname(__file__))

def read(*parts):
    return codecs.open(os.path.join(here, *parts), 'r').read()

def find_version(*file_paths):
    version_file = read(*file_paths)
    version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]",
                              version_file, re.M)
    if version_match:
        return version_match.group(1)
    raise RuntimeError("Unable to find version string.")

# Set a default description just in case we don't find it in the readme.
description = 'a tool to chain tools into toolchains'

# Pick the desired sections out of the readme for use in the long description,
# and also look for the short description in the readme header.
readme_orig = read('README.rst')
readme_sections = set(['blurb_section', 'documentation_section'])
readme = ''
section = None
include_line = False
for readme_line in readme_orig.splitlines(True):
    is_anchor = ANCHOR_PATTERN.match(readme_line)
    if is_anchor:
        section = is_anchor.group(1)
        include_line = False
        continue
    if section == 'header_section':
        if readme_line.startswith('chaintool:'):
            description = readme_line[10:].strip()
    if include_line:
        readme = readme + readme_line
    elif section in readme_sections:
        include_line = True

# Form long description from select readme sections + history/changelog.
long_description = readme + read('HISTORY.rst')

setuptools.setup(
    name = "chaintool",
    version = find_version("src/chaintool/__init__.py"),
    package_dir = {"": "src"},
    packages = setuptools.find_packages(where="src"),
    include_package_data = True,
    author = 'Joel Baxter',
    author_email = 'joel.baxter@neogeographica.com',
    url = 'https://github.com/neogeographica/chaintool',
    description = description,
    long_description = long_description,
    long_description_content_type = 'text/x-rst',
    classifiers = [
        'Development Status :: 2 - Pre-Alpha',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Topic :: Utilities',
    ],
    platforms = 'any',
    license = 'GPLv3',
    zip_safe = True,
    python_requires = '>=3.7',
    install_requires = [
        'appdirs>=1.4.4',
        'colorama>=0.4.4',
        'filelock>=3.0.12',
        'psutil>=5.8.0',
        'PyYAML>=5.4.1',
    ],
    entry_points = {
        'console_scripts': [
            'chaintool = chaintool.cli:main',
        ],
    },
    keywords = [''], # ???
)
