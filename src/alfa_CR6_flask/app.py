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

from flask_admin.base import MenuLink, Admin # pylint: disable=import-error

from waitress import serve       # pylint: disable=import-error

from alfa_CR6_backend.globals import import_settings
from alfa_CR6_backend.models import (Order, Jar, Event, Document, set_global_session, apply_table_alterations)
from alfa_CR6_flask.admin_views import (AdminIndexView, OrderModelView, JarModelView, EventModelView, DocumentModelView)
from alfa_CR6_flask.api import init_restless_api, init_restful_api
from alfa_CR6_flask.remote_ui import init_remote_ui

SETTINGS = import_settings()


def _gettext(s):
    return s


def init_db(app):

    db = flask_sqlalchemy.SQLAlchemy()
    db.init_app(app)
    set_global_session(db.session)
    engine = db.get_engine(app=app)
    apply_table_alterations(engine)

    return db


def init_admin(app, db):

    index_view_ = AdminIndexView(db, url='/')

    admin_ = flask_admin.base.Admin(app, name=_gettext('Alfa_CRX'), template_mode='bootstrap3', index_view=index_view_)

    admin_.add_view(OrderModelView(Order, db.session))
    admin_.add_view(JarModelView(Jar, db.session, "Can"))
    admin_.add_view(EventModelView(Event, db.session))
    admin_.add_view(DocumentModelView(Document, db.session))

    admin_.add_link(MenuLink(name=_gettext('Manuals'), url='/manual_index'))

    return admin_


def main():

    try:
        logging.basicConfig(
            force=True, level=SETTINGS.LOG_LEVEL,
            format="[%(asctime)s]%(levelname)s %(funcName)s() %(filename)s:%(lineno)d %(message)s")
    except ValueError:
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

    init_restless_api(app, db)
    init_restful_api(app, db)

    init_remote_ui(app, db)

    HOST, PORT = '0.0.0.0', 8090
    logging.warning("start serving admin UI on http://{}:{}".format(HOST, PORT))
    serve(app, host=HOST, port=PORT)
