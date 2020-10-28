# coding: utf-8

import os
import glob

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, '__version__'), encoding='utf-8') as f:
    __version__ = f.read().strip()


def main():
    setup(
        name='alfa_CR6',
        version=__version__,
        description='UI for alfa CR6',
        url='https://gitlab.com/freelands2019/alfa_cr6',
        author='alfadispenser srl',
        author_email='giovanniangeli@alfadispenser.com',
        classifiers=[
            'Development Status :: 3 - Alpha',
            'Programming Language :: Python :: 3',
            "License :: OSI Approved :: MIT License",
            "Operating System :: POSIX :: Linux",
        ],
        packages=find_packages(where='src'),
        package_dir={'': 'src'},
        data_files=[
            ('alfa_CR6_ui/ui', list(glob.glob('src/alfa_CR6_ui/ui/*.ui'))),
            ('alfa_CR6_ui/images', list(glob.glob('src/alfa_CR6_ui/icons/*'))),
            ('alfa_CR6_ui/icons', list(glob.glob('src/alfa_CR6_ui/images/*'))),
        ],
        include_package_data=True,
        scripts=[
            'bin/alfa_CR6',
            'bin/alfa_CR6_test',
        ],
        install_requires=[
            'websockets',
            'SQLAlchemy',
            'jsonschema',
        ],
    )


if __name__ == '__main__':
    main()
