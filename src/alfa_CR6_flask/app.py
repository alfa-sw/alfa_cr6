# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name
# pylint: disable=broad-except

import os
import sys
import logging
import json
import datetime
import traceback
import tempfile
import subprocess

from werkzeug.utils import secure_filename  # pylint: disable=import-error

from flask import Markup, Flask, redirect, flash, request  # pylint: disable=import-error

import flask_sqlalchemy          # pylint: disable=import-error
import flask_admin               # pylint: disable=import-error
import flask_admin.contrib.sqla  # pylint: disable=import-error
from flask_admin.contrib.sqla.filters import FilterInList  # pylint: disable=import-error

from waitress import serve       # pylint: disable=import-error

from alfa_CR6_backend.models import Order, Jar, Event, Document, set_global_session
from alfa_CR6_backend.globals import import_settings


def _handle_CRX_stream_upload(stream, filename):

    flash_msgs = ['cannot create temp file']
    with tempfile.NamedTemporaryFile() as f:
        flash_msgs = []
        splitext = os.path.splitext(filename)
        splitname = os.path.split(filename)
        logging.info("splitext:{}, splitname:{}".format(splitext, splitname))

        logging.warning(filename)
        content = stream.read()
        try:
            cmd_ = ''
            cmd_ += '. /opt/alfa_cr6/venv/bin/activate;'
            cmd_ += 'python -c "from alfa_CR6_backend.globals import import_settings; s = import_settings(); print(s.WEBENGINE_DOWNLOAD_PATH, )"'
            WEBENGINE_DOWNLOAD_PATH = subprocess.check_output(
                cmd_, shell=True, stderr=subprocess.STDOUT).decode()
            pth_ = os.path.join(WEBENGINE_DOWNLOAD_PATH.strip(), filename)
            open(pth_, 'wb').write(content)
            flash_msgs.append('uploaded CRX file:{} to:{}.'.format(f.name, pth_))
        except BaseException:
            logging.error(traceback.format_exc())

    return flash_msgs


def _gettext(s):
    return s


def init_db(app):

    db = flask_sqlalchemy.SQLAlchemy()
    db.init_app(app)
    return db


def init_admin_and_define_view_classes(app, db):    # pylint: disable=too-many-statements

    settings = import_settings()

    class FilterOrderByJarStatusInList(FilterInList):  # pylint: disable=too-few-public-methods
        def apply(self, query, value, alias=None): # pylint: disable=unused-argument, no-self-use
            return query.join(Jar).filter(Jar.status.in_(value))
            # ~ return query.filter(self.get_column(alias).in_(value))

    class CRX_AdminResources(flask_admin.AdminIndexView):

        @flask_admin.expose("/")
        @flask_admin.expose("/home")
        @flask_admin.expose("/index")
        def index(self, ):
            template = "/index.html"

            links = []
            for i, item in enumerate(settings.MACHINE_HEAD_IPADD_PORTS_LIST):
                if item:
                    ip, _, ph = item
                    l = Markup('<a href="http://{}:{}/admin" > HEAD {} admin </a>'.format(ip, ph, i))
                    links.append(l)

            logging.warning(f"request.host:{request.host}")
            ctx = {
                'links': links,
                'ws_ip_addr_and_port': "{}:{}".format(request.host.split(':')[0], 13000),
                'alfa40_admin_url': "http://{}:{}/admin".format(request.host.split(':')[0], 8080),
                'current_language': settings.LANGUAGE,
            }

            return self.render(template, **ctx)

        @flask_admin.expose('/upload', methods=('POST',))
        def upload(self):     # pylint: disable=no-self-use

            flash_msgs = []
            try:
                if request.method == 'POST':
                    for stream in request.files.getlist('file'):
                        filename = secure_filename(stream.filename)
                        flash_msgs = flash_msgs + _handle_CRX_stream_upload(stream, filename)
            except Exception as exc:  # pylint: disable=broad-except
                flash_msgs.append('Error trying to upload files: {}'.format(exc))
                logging.error(traceback.format_exc())

            if flash_msgs:
                flash(Markup("<br/>".join(flash_msgs)))

            logging.warning("flash_msgs:{}".format(flash_msgs))
            ret = redirect('/index')
            logging.warning("ret:{}".format(ret))
            return ret

    class CRX_ModelView(flask_admin.contrib.sqla.ModelView):

        column_default_sort = ('date_created', True)

        can_export = True
        export_max_rows = 10000
        export_types = ['csv', 'xls', 'json']

        named_filter_urls = True
        can_view_details = True
        export_limit = 10 * 1000

        def display_time_to_local_tz(self, context, obj, name):   # pylint: disable=unused-argument,no-self-use

            value = getattr(obj, name)
            # ~ value_ = value.replace(tzinfo=datetime.timezone.utc).strftime("%Y-%m-%d %I:%M:%S:%f (%Z)")
            value_local = value.replace(tzinfo=datetime.timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S:%f (%Z)")
            return Markup(value_local)

        def display_json_properties(self, context, obj, name):  # pylint: disable=unused-argument,no-self-use

            try:
                json_properties = json.loads(obj.json_properties)
            except Exception:
                json_properties = traceback.format_exc()

            html_ = "<div>"
            for k, v in json_properties.items():
                html_ += "<div><b>{}</b>:{}</div>".format(k, v)
            html_ += "</div>"

            return Markup(html_)

        column_formatters = {
            'json_properties': display_json_properties,
            'date_created': display_time_to_local_tz,
            'date_modified': display_time_to_local_tz, }

        column_filters = (
            'date_created',
            'description',)

        column_searchable_list = (
            'json_properties',
            'description',)

        column_exclude_list = (
            'json_properties',)

    class EventModelView(CRX_ModelView):
        column_filters = (
            'name',
            'level',
            'severity',
            'source',
            'date_created',
            'description',)

        column_searchable_list = (
            'name',
            'level',
            'date_created',
            'description',)

    class JarModelView(CRX_ModelView):
        column_filters = (
            'status',
            'order.order_nr',
            'date_created',
            'description',)

        column_searchable_list = (
            'status',
            'date_created',
            'description',)

    class OrderModelView(CRX_ModelView):

        column_list = (
            'order_nr',
            'date_created',
            'date_modified',
            'description',
            'jars')

        column_labels = dict(jars='Cans status')

        column_filters = (
            FilterOrderByJarStatusInList(column=None, name='can status', options=[(c, c) for c in Jar.status_choices]),
            'order_nr',
            'date_created',
            'description',)

        column_searchable_list = (
            'order_nr',
            'date_created',
            'description',)

        def display_description(self, context, obj, name): # pylint: disable=unused-argument, no-self-use
            description = getattr(obj, 'description')
            json_properties = getattr(obj, 'json_properties')

            _html = ''
            try:
                meta = json.loads(json_properties).get("meta", {})
                file_name = meta.get("file name")
                if file_name:
                    _html += f"{file_name}"
                if description:
                    _html += f", {description}"
            except Exception:
                _html = description
                logging.warning(traceback.format_exc())

            return Markup(_html)

        def display_jars_status(self, context, obj, name): # pylint: disable=unused-argument, no-self-use
            jars = getattr(obj, 'jars')
            jars_statuses = {j.status for j in jars}

            _html = ''
            try:
                _html += f"{jars_statuses}"
            except Exception:
                _html = jars
                logging.warning(traceback.format_exc())

            return Markup(_html)

        column_formatters = CRX_ModelView.column_formatters.copy()
        column_formatters.update({
            'description': display_description,
            'jars': display_jars_status,
        })

        # Need this so the filter options are always up-to-date
        @flask_admin.expose('/')
        def index_view(self):
            self._refresh_filters_cache()
            return super().index_view()

    class DocumentModelView(CRX_ModelView):

        column_filters = (
            'name',
            'type',
            'description',
            'json_properties',
            'date_created',)

        column_searchable_list = (
            'name',
            'type',
            'description',
            'json_properties',)

    index_view_ = CRX_AdminResources(url='/')    # pylint: disable=undefined-variable
    admin_ = flask_admin.base.Admin(app, name=_gettext('Alfa_CRX'), template_mode='bootstrap3', index_view=index_view_)

    admin_.add_view(JarModelView(Jar, db.session, "Can"))            # pylint: disable=undefined-variable
    admin_.add_view(OrderModelView(Order, db.session))        # pylint: disable=undefined-variable
    admin_.add_view(EventModelView(Event, db.session))        # pylint: disable=undefined-variable
    admin_.add_view(DocumentModelView(Document, db.session))  # pylint: disable=undefined-variable


def main():

    settings = import_settings()

    logging.basicConfig(
        stream=sys.stdout, level=settings.LOG_LEVEL,
        format="[%(asctime)s]%(levelname)s %(funcName)s() %(filename)s:%(lineno)d %(message)s")

    app = Flask('alfa_CR6_flask')
    sqlalchemy_database_uri_ = settings.SQLITE_CONNECT_STRING
    logging.warning(f'sqlalchemy_database_uri_ :{sqlalchemy_database_uri_ }')
    # ~ app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + '/opt/alfa_cr6/data/CRx_v0_SW.sqlite'
    app.config['SQLALCHEMY_DATABASE_URI'] = sqlalchemy_database_uri_
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or '123456790'

    db = init_db(app)

    set_global_session(db.session)

    init_admin_and_define_view_classes(app, db)

    HOST, PORT = '0.0.0.0', 8090
    logging.warning("start serving admin UI on http://{}:{}".format(HOST, PORT))
    serve(app, host=HOST, port=PORT)
