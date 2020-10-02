import pathlib, glob
from setuptools import setup, find_packages

def main():
    packages_ = find_packages(where='src')
    package_dir = {
        'alfa_CR6': 'src/alfa_CR6',
    }
    glob.glob('src/alfa_CR6/*.ui')
    setup (
        name='alfa_CR6',
        version='1.0',
        description='ALFA CR& Project',
        packages=packages_,
        package_dir=package_dir,
        package_data={'alfa_CR6': glob.glob('src/alfa_CR6/*.ui')},
        include_package_data=True,
    )

if __name__ == '__main__':
    main()
