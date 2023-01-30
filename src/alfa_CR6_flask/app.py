# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name
# pylint: disable=broad-except
# pylint: disable=logging-fstring-interpolation, consider-using-f-string

import os
import sys
import logging

from flask import Flask  # pylint: disable=import-error

from waitress import serve       # pylint: disable=import-error

from alfa_CR6_backend.globals import import_settings
from alfa_CR6_backend.models import init_db
from alfa_CR6_flask.admin_views import init_admin
from alfa_CR6_flask.api import init_restless_api, init_restful_api, init_ad_hoc_api
from alfa_CR6_flask.remote_ui import init_remote_ui

SETTINGS = import_settings()


def main():

    logging.basicConfig(
        stream=sys.stdout, level=SETTINGS.LOG_LEVEL,
        format="[%(asctime)s]%(levelname)s %(funcName)s() %(filename)s:%(lineno)d %(message)s")

    app = Flask('alfa_CR6_flask')

    sqlalchemy_database_uri_ = SETTINGS.SQLITE_CONNECT_STRING
    logging.warning(f'sqlalchemy_database_uri_ :{sqlalchemy_database_uri_ }')

    app.config['SQLALCHEMY_DATABASE_URI'] = sqlalchemy_database_uri_
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or '123456790'

    db = init_db(app)

    admin = init_admin(app, db)
    logging.warning(f'admin:{admin}')

    init_restless_api(app, db)
    init_restful_api(app, db)
    init_ad_hoc_api(app, db)

    init_remote_ui(app, db)

    HOST, PORT = '0.0.0.0', 8090
    logging.warning("start serving admin UI on http://{}:{}".format(HOST, PORT))
    serve(app, host=HOST, port=PORT)
