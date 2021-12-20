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
import json
import datetime
import traceback
import tempfile

from flask import (Markup, Flask, redirect, flash, request, send_file)  # pylint: disable=import-error

import flask_sqlalchemy  # pylint: disable=import-error
import flask_admin  # pylint: disable=import-error
from flask_admin.contrib.sqla import ModelView  # pylint: disable=import-error
from flask_admin.contrib.sqla.filters import FilterInList, FilterNotInList  # pylint: disable=import-error

from waitress import serve       # pylint: disable=import-error

from alfa_CR6_backend.models import (Order, Jar, Event, Document, set_global_session)
from alfa_CR6_backend.globals import (import_settings, CONF_PATH)

SETTINGS = import_settings()

def _to_html_table(_obj, rec_lev=0):

    max_rec_lev = 3
    _html = ""
    _class = "table-striped table-bordered"
    if isinstance(_obj, dict) and rec_lev < max_rec_lev:
        _html = f'<table class="{_class}"><tr>'
        _html += '</tr><tr>'.join(
            ['<td>{}:</td> <td>{}</td>'.format(k, _to_html_table(v, rec_lev+1)) for k, v in _obj.items()])
        _html += '</tr></table>'
    elif isinstance(_obj, list) and rec_lev < max_rec_lev:
        _html = f'<table class="{_class}"><tr>'
        _html += '</tr><tr>'.join(
            ['<td>{}</td>'.format(_to_html_table(v, rec_lev+1)) for v in _obj])
        _html += '</tr></table>'
    else:
        _html += str(_obj)

    return _html

def _gettext(s):
    return s


class FilterOrderByJarStatusInList(FilterInList):  # pylint: disable=too-few-public-methods
    def apply(self, query, value, alias=None): # pylint: disable=unused-argument, no-self-use
        return query.join(Jar).filter(Jar.status.in_(value))

class FilterOrderByJarStatusNotInList(FilterNotInList):  # pylint: disable=too-few-public-methods
    def apply(self, query, value, alias=None): # pylint: disable=unused-argument, no-self-use
        return query.join(Jar).filter(~Jar.status.in_(value))

class FilterOrderByJarPositionInList(FilterInList):  # pylint: disable=too-few-public-methods
    def apply(self, query, value, alias=None): # pylint: disable=unused-argument, no-self-use
        return query.join(Jar).filter(Jar.position.in_(value))

class FilterOrderByJarPositionNotInList(FilterNotInList):  # pylint: disable=too-few-public-methods
    def apply(self, query, value, alias=None): # pylint: disable=unused-argument, no-self-use
        return query.join(Jar).filter(~Jar.position.in_(value))

class CRX_ModelView(ModelView):

    list_template = 'admin/list.html'

    named_filter_urls = True

    column_default_sort = ('date_created', True)

    can_export = True
    export_max_rows = 10000
    export_types = ['csv', 'xls', 'json']

    named_filter_urls = True
    can_view_details = True
    export_limit = 10 * 1000

    def display_time_to_local_tz(self, context, obj, name):   # pylint: disable=unused-argument,no-self-use

        value = getattr(obj, name)
        value_local = value.replace(tzinfo=datetime.timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S:%f (%Z)")
        return Markup(value_local)

    def display_json_properties(self, context, obj, name):  # pylint: disable=unused-argument,no-self-use

        try:
            json_properties = json.loads(obj.json_properties)
        except Exception:
            json_properties = {'exc': traceback.format_exc()}

        html_ = "<div>"
        html_ += _to_html_table(json_properties)
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

    column_list = (
        'order',
        'index',
        'position',
        'status',
        'date_created',
        'date_modified',
        'order_description',)

    column_filters = (
        'status',
        'position',
        'order.order_nr',
        'date_created',
        'description',)

    column_searchable_list = (
        'status',
        'position',
        'date_created',
        'description',)

    column_editable_list = (
        'position',
        'status',
        'description',)

    form_choices = {
        'position': [(c, c) for c in Jar.position_choices],
        'status': [(c, c) for c in Jar.status_choices],}


    def _display_order(self, context, obj, name): # pylint: disable=no-self-use, unused-argument
        order = getattr(obj, 'order')

        link = f"/order/details/?id={order.id}"
        _html = ''
        try:
            _html += f"""<a href="{link}">{order.order_nr}</a>"""
        except Exception:
            _html = order
            logging.warning(traceback.format_exc())

        return Markup(_html)

    def _display_order_description(self, context, obj, name): # pylint: disable=no-self-use, unused-argument

        order = getattr(obj, 'order')
        return OrderModelView.display_description(context, order, name)

    column_formatters = CRX_ModelView.column_formatters.copy()
    column_formatters.update({
        'order': _display_order,
        'order_description': _display_order_description,
    })


class OrderModelView(CRX_ModelView):

    column_list = (
        'order_nr',
        'can status',
        'can position',
        'date_created',
        'date_modified',
        'description',
    )

    column_labels = dict(jars='Cans status')

    column_filters = (
        FilterOrderByJarStatusInList(column=None, name='can status', options=[(c, c) for c in Jar.status_choices]),
        FilterOrderByJarStatusNotInList(column=None, name='can status', options=[(c, c) for c in Jar.status_choices]),
        FilterOrderByJarPositionInList(column=None, name='can position', options=[(c, c) for c in Jar.position_choices]),
        FilterOrderByJarPositionNotInList(column=None, name='can position', options=[(c, c) for c in Jar.position_choices]),
        'order_nr',
        'date_created',
        'description',)

    column_searchable_list = (
        'order_nr',
        'date_created',
        'description',)

    @staticmethod
    def display_description(context, obj, name): # pylint: disable=unused-argument
        description = getattr(obj, 'description', '')
        json_properties = getattr(obj, 'json_properties')

        _html = ''
        try:
            meta = json.loads(json_properties).get("meta") or {}
            file_name = meta.get("file name", '')
            _html += f"{file_name}  {description}"
        except Exception:
            _html = description
            logging.warning(traceback.format_exc())

        return Markup(_html)

    def _display_description(self, context, obj, name): # pylint: disable=unused-argument
        return self.display_description(context, obj, name)

    def _display_jar_status(self, context, obj, name): # pylint: disable=no-self-use, unused-argument
        jars = getattr(obj, 'jars')

        jar_status_list = [j.status for j in jars]
        jar_statuses = [(s, jar_status_list.count(s)) for s in set(jar_status_list)]
        jar_statuses = sorted(jar_statuses, key=lambda x: x[1])

        link = f"/jar/?sort=1&flt0_order_order_order_nr_equals={getattr(obj, 'order_nr')}"

        _html = ''
        try:
            _html += f"""<a href="{link}">{'<br/>'.join([str(i) for i in jar_statuses])}</a>"""
        except Exception:
            _html = jars
            logging.warning(traceback.format_exc())

        return Markup(_html)

    def _display_jar_position(self, context, obj, name): # pylint: disable=no-self-use, unused-argument
        jars = getattr(obj, 'jars')

        jar_position_list = [j.position for j in jars]
        jar_positions = [(s, jar_position_list.count(s)) for s in set(jar_position_list)]
        jar_positions = sorted(jar_positions, key=lambda x: x[1])

        _html = ''
        try:
            _html += f"{'<br/>'.join([str(i) for i in jar_positions])}"
        except Exception:
            _html = jars
            logging.warning(traceback.format_exc())

        return Markup(_html)

    column_formatters = CRX_ModelView.column_formatters.copy()
    column_formatters.update({
        'description': _display_description,
        'can status': _display_jar_status,
        'can position': _display_jar_position,
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


class CRX_AdminResources(flask_admin.AdminIndexView):

    @flask_admin.expose("/")
    @flask_admin.expose("/home")
    @flask_admin.expose("/index")
    def index(self, ):
        template = "/index.html"

        links = []
        for i, item in enumerate(SETTINGS.MACHINE_HEAD_IPADD_PORTS_LIST):
            if item:
                ip, _, ph = item
                l = Markup('<a href="http://{}:{}/admin" > HEAD {} admin </a>'.format(ip, ph, i))
                links.append(l)

        logging.warning(f"request.host:{request.host}")
        ctx = {
            'links': links,
            'ws_ip_addr_and_port': "{}:{}".format(request.host.split(':')[0], 13000),
            'alfa40_admin_url': "http://{}:{}/admin".format(request.host.split(':')[0], 8080),
            'current_language': SETTINGS.LANGUAGE,
        }

        return self.render(template, **ctx)

    @flask_admin.expose('/upload', methods=('POST',))
    def upload(self):     # pylint: disable=no-self-use

        flash_msgs = []
        try:
            if request.method == 'POST':
                for stream in request.files.getlist('file'):
                    split_ext = os.path.splitext(stream.filename)
                    logging.warning(f"stream.mimetype:{stream.mimetype}, stream.filename:{stream.filename}, split_ext:{split_ext}.")

                    if "app_settings.py" in stream.filename.lower():
                        with open(os.path.join(SETTINGS.CONF_PATH, 'app_settings.py'), 'wb') as f:
                            f.write(stream.read())
                        flash_msgs.append("app settings overwritten. {}".format(stream.filename))

                    elif split_ext[1:] and split_ext[1] == '.sqlite':
                        orig_pth = SETTINGS.SQLITE_CONNECT_STRING.split('///')[1]
                        logging.warning("orig_pth:{}".format(orig_pth))
                        if os.path.split(orig_pth)[1] in os.path.split(stream.filename)[1]:
                            back_pth = orig_pth + ".BACK"
                            temp_pth = orig_pth + ".TEMP"
                            with open(temp_pth, 'wb') as f:
                                f.write(stream.read())
                            os.system("cp -a {} {}".format(orig_pth, back_pth))
                            os.system("cp -a {} {}".format(temp_pth, orig_pth))
                            flash_msgs.append('uploaded new sqlite db: {}.'.format(stream.filename))
                        else:
                            msg = 'ERROR invlaid file name {}. Check db version'.format(stream.filename)
                            flash_msgs.append(msg)
                            logging.error(msg)
                    else:
                        msg = 'unknown file {}.'.format(stream.filename)
                        flash_msgs.append(msg)

        except Exception as exc:  # pylint: disable=broad-except
            flash_msgs.append('Error trying to upload files: {}'.format(exc))
            logging.error(traceback.format_exc())

        if flash_msgs:
            flash(Markup("<br/>".join(flash_msgs)))

        logging.warning("flash_msgs:{}".format(flash_msgs))
        ret = redirect('/index')
        return ret

    @flask_admin.expose('/download', methods=('GET',))
    def download(self):     # pylint: disable=no-self-use

        data_set_name = request.args.get('data_set_name', 'full_db')
        # ~ compress_data = request.args.get('compress_data')
        # ~ export_limit = request.args.get('export_limit', 50 * 1000)

        logging.warning("data_set_name:{}".format(data_set_name))

        flash_msgs = []
        file_to_send = None
        out_fname = None
        try:
            if data_set_name.lower() == 'full_db':
                file_to_send = SETTINGS.SQLITE_CONNECT_STRING.split('///')[1]
                out_fname = '{}_{}'.format(datetime.datetime.now().isoformat(timespec='seconds'), os.path.basename(file_to_send))
            elif data_set_name.lower() == 'app_settings':
                file_to_send = os.path.join(CONF_PATH, "app_settings.py")
                out_fname = '{}_{}'.format(datetime.datetime.now().isoformat(timespec='seconds'), os.path.basename(file_to_send))
            else:
                flash_msgs.append("unknown data_set_name: {}".format(data_set_name.lower()))
        except Exception as exc:  # pylint: disable=broad-except
            flash_msgs.append('Error trying to download files: {}'.format(exc))
            logging.error(traceback.format_exc())

        if flash_msgs:
            flash(Markup("<br/>".join(flash_msgs)))

        if file_to_send and out_fname:
            logging.warning("file_to_send:{}, out_fname:{}".format(file_to_send, out_fname))
            return send_file(
                file_to_send,
                mimetype='application/octet-stream',
                as_attachment=True,
                attachment_filename=out_fname
            )

        logging.warning("flash_msgs:{}".format(flash_msgs))
        ret = redirect('/index')
        return ret


def init_db(app):

    db = flask_sqlalchemy.SQLAlchemy()
    db.init_app(app)
    set_global_session(db.session)
    return db

def init_admin(app):

    db = init_db(app)

    index_view_ = CRX_AdminResources(url='/')
    admin_ = flask_admin.base.Admin(app, name=_gettext('Alfa_CRX'), template_mode='bootstrap3', index_view=index_view_)

    admin_.add_view(OrderModelView(Order, db.session))
    admin_.add_view(JarModelView(Jar, db.session, "Can"))
    admin_.add_view(EventModelView(Event, db.session))
    admin_.add_view(DocumentModelView(Document, db.session))


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

    init_admin(app)

    HOST, PORT = '0.0.0.0', 8090
    logging.warning("start serving admin UI on http://{}:{}".format(HOST, PORT))
    serve(app, host=HOST, port=PORT)
