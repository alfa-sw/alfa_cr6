# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=invalid-name

import os
import glob

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, '__version__'), encoding='utf-8') as f:
    __version__ = f.read().strip()

__app_name__ = 'alfa_CR6'

INSTALL_REQUIRES = [
    'websockets',
    'SQLAlchemy<1.4.0', # api changed in 1.4.0
    'jsonschema',
    'python-barcode<0.14.0',
    # ~ 'Pillow',
    'aiohttp',
    'flask',
    'flask_sqlalchemy<3.0.0',
    'flask_admin',
    'waitress',
    'python-magic',
    'xmltodict',
    'evdev',
    'redis<4.0.0',
    'iso8601',
    # ~ 'PyQt5',
    # ~ 'PyQtWebEngine',
    # ~ 'flask-restless-swagger-2',
    'Flask-Restless-NG',
    'flask_restful',
]


def main():
    setup(
        name=__app_name__,
        version=__version__,
        description='UI for alfa CR6',
        url='https://gitlab.com/alfa-sw/alfa_cr6',
        author='giovanni angeli per alfadispenser srl',
        author_email='giovanniangeli@alfadispenser.com',
        python_requires='>=3.7.0',
        classifiers=[
            'Development Status :: 3 - Alpha',
            'Programming Language :: Python :: 3',
            "License :: OSI Approved :: MIT License",
            "Operating System :: POSIX :: Linux",
        ],
        packages=find_packages(where='src'),
        package_dir={'': 'src'},
        data_files=[
            ('alfa_CR6_backend/schemas', list(glob.glob('src/alfa_CR6_backend/schemas/*'))),
            ('alfa_CR6_backend/templates', list(glob.glob('src/alfa_CR6_backend/templates/*'))),
            ('alfa_CR6_flask/static/images', list(glob.glob('src/alfa_CR6_flask/static/images/*'))),
            # ~ ('alfa_CR6_flask/static/admin', list(glob.glob('src/alfa_CR6_flask/static/admin/*.*'))),
            ('alfa_CR6_flask/static', list(glob.glob('src/alfa_CR6_flask/static/*.*'))),
            ('alfa_CR6_flask/static/remote_ui', list(glob.glob('src/alfa_CR6_flask/static/remote_ui/*.*'))),
            ('alfa_CR6_flask/static/remote_ui/images', list(glob.glob('src/alfa_CR6_flask/static/remote_ui/images/*'))),
            ('alfa_CR6_flask/templates', list(glob.glob('src/alfa_CR6_flask/templates/*.html'))),
            ('alfa_CR6_flask/templates/admin', list(glob.glob('src/alfa_CR6_flask/templates/admin/*.html'))),
            ('alfa_CR6_frontend/help', list(glob.glob('src/alfa_CR6_frontend/help/*'))),
            ('alfa_CR6_frontend/images', list(glob.glob('src/alfa_CR6_frontend/images/*'))),
            ('alfa_CR6_frontend/keyboard', list(glob.glob('src/alfa_CR6_frontend/keyboard/*'))),
            ('alfa_CR6_frontend/ui', list(glob.glob('src/alfa_CR6_frontend/ui/*'))),
            ('alfa_CR6_test/fixtures', list(glob.glob('src/alfa_CR6_test/fixtures/*'))),
        ],
        include_package_data=True,
        scripts=[
            'bin/alfa_CR6',
            'bin/alfa_CR6_flask',
            'bin/alfa_CR6_test',
        ],
        install_requires=INSTALL_REQUIRES,
    )


if __name__ == '__main__':
    main()
