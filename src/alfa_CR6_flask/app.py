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

import flask_sqlalchemy  # pylint: disable=import-error
import flask_admin  # pylint: disable=import-error

from waitress import serve       # pylint: disable=import-error

from alfa_CR6_backend.globals import import_settings
from alfa_CR6_backend.models import (Order, Jar, Event, Document, set_global_session)
from alfa_CR6_flask.admin_views import (AdminIndexView, OrderModelView, JarModelView, EventModelView, DocumentModelView)
from alfa_CR6_flask.api import init_restless_api

SETTINGS = import_settings()


def _gettext(s):
    return s


def init_db(app):

    db = flask_sqlalchemy.SQLAlchemy()
    db.init_app(app)
    set_global_session(db.session)
    return db


def init_admin(app, db):

    index_view_ = AdminIndexView(db, url='/')

    admin_ = flask_admin.base.Admin(app, name=_gettext('Alfa_CRX'), template_mode='bootstrap3', index_view=index_view_)

    admin_.add_view(OrderModelView(Order, db.session))
    admin_.add_view(JarModelView(Jar, db.session, "Can"))
    admin_.add_view(EventModelView(Event, db.session))
    admin_.add_view(DocumentModelView(Document, db.session))

    return admin_


def main():

    logging.basicConfig(
        stream=sys.stdout, level=SETTINGS.LOG_LEVEL,
        format="[%(asctime)s]%(levelname)s %(funcName)s() %(filename)s:%(lineno)d %(message)s")

    app = Flask('alfa_CR6_flask')
    sqlalchemy_database_uri_ = SETTINGS.SQLITE_CONNECT_STRING
    logging.warning(f'sqlalchemy_database_uri_ :{sqlalchemy_database_uri_ }')
    # ~ app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + '/opt/alfa_cr6/data/CRx_v0_SW.sqlite'
    app.config['SQLALCHEMY_DATABASE_URI'] = sqlalchemy_database_uri_
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or '123456790'

    db = init_db(app)

    admin = init_admin(app, db)
    logging.warning(f'admin:{admin}')

    api_manager = init_restless_api(app, db)
    # ~ logging.warning(f'api_manager:{api_manager}'[:200])

    HOST, PORT = '0.0.0.0', 8090
    logging.warning("start serving admin UI on http://{}:{}".format(HOST, PORT))
    serve(app, host=HOST, port=PORT)
