
import os
import glob

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))

with open(os.path.join(here, '__version__'), encoding='utf-8') as f:
    __version__ = f.read().strip()

def main():
    packages_ = find_packages(where='src')
    package_dir = {
        'alfa_CR6': 'src/alfa_CR6',
    }
    setup(
        name='alfa_CR6',
        version=__version__,
        description='UI for alfa CR6',
        packages = find_packages('src'),
        package_dir = {'': 'src'},
        data_files=[
            # ~ ('alfa_CR6/ui', list(glob.glob('src/alfa_CR6/ui/*'))),
            ('alfa_CR6/ui', list(glob.glob('src/alfa_CR6/ui/*.ui'))),
            ('alfa_CR6/images', list(glob.glob('src/alfa_CR6/icons/*'))),
            ('alfa_CR6/icons', list(glob.glob('src/alfa_CR6/images/*'))),
        ],
        include_package_data=True,
        scripts=['bin/alfa_CR6'],
        install_requires = [
            'PyQt5',
            'PyQt5-sip',
            'PyQtWebEngine',
            'websockets',
        ],
    )


if __name__ == '__main__':
    main()
