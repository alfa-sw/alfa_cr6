import glob
from setuptools import setup, find_packages


def main():
    packages_ = find_packages(where='src')
    package_dir = {
        'alfa_CR6': 'src/alfa_CR6',
    }
    setup(
        name='alfa_CR6',
        version='1.2',
        description='ALFA CR& Project',
        packages=packages_,
        package_dir=package_dir,
        package_data={'alfa_CR6/ui': glob.glob('src/alfa_CR6/ui/*')},
        data_files=[('alfa_CR6/ui', list(glob.glob('src/alfa_CR6/ui/*'))),
                    ('alfa_CR6/ui', list(glob.glob('src/alfa_CR6/ui/*.ui'))),
                    ('alfa_CR6/images', list(glob.glob('src/alfa_CR6/icons/*'))),
                    ('alfa_CR6/icons', list(glob.glob('src/alfa_CR6/images/*'))),

                    ],
        include_package_data=True,
    )


if __name__ == '__main__':
    main()
