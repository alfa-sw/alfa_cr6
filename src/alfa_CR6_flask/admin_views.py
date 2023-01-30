# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name
# pylint: disable=broad-except
# pylint: disable=logging-fstring-interpolation, consider-using-f-string

import logging
import json
import datetime
import traceback

from flask import (Markup, request)  # pylint: disable=import-error

import flask_admin  # pylint: disable=import-error
from flask_admin.menu import MenuLink

from flask_admin.contrib.sqla import ModelView  # pylint: disable=import-error
from flask_admin.contrib.sqla.filters import FilterInList, FilterNotInList  # pylint: disable=import-error

from alfa_CR6_backend.models import Jar
from alfa_CR6_backend.globals import (LANGUAGE_MAP, import_settings)
from alfa_CR6_backend.models import (Order, Jar, Event, Document, set_global_session, apply_table_alterations)

SETTINGS = import_settings()

def _gettext(s):
    return s

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

class Base_ModelView(ModelView):

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

class EventModelView(Base_ModelView):
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

class JarModelView(Base_ModelView):

    column_list = (
        'order',
        'index',
        'position',
        'status',
        'date_created',
        'date_modified',
        'order_description',
        # ~ 'is_deleted',
        'order_file_name',)

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

    form_excluded_columns = ('order', )

    def _display_order(self, context, obj, name): # pylint: disable=no-self-use, unused-argument
        order = getattr(obj, 'order')

        try:
            _html = order and f"""<a href="/order/details/?id={order.id}">{order.order_nr}</a>"""
        except Exception:
            _html = order
            logging.warning(traceback.format_exc())

        return Markup(_html)

    def _display_order_description(self, context, obj, name): # pylint: disable=no-self-use, unused-argument

        order = getattr(obj, 'order')
        return order and order.description

    def _display_order_file_name(self, context, obj, name): # pylint: disable=no-self-use, unused-argument

        order = getattr(obj, 'order')
        return order and order.file_name

    column_formatters = Base_ModelView.column_formatters.copy()
    column_formatters.update({
        'order': _display_order,
        'order_description': _display_order_description,
        'order_file_name': _display_order_file_name,
    })


class OrderModelView(Base_ModelView):

    column_list = (
        'order_nr',
        'status',
        'can status',
        'can position',
        'date_created',
        'date_modified',
        'description',
        'file_name',
        'is_deleted',
    )

    # ~ column_exclude_list = ('has_not_deleted', )

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

    form_excluded_columns = ('jars', )

    def _display_status(self, context, obj, name): # pylint: disable=no-self-use, unused-argument

        _html = ''
        try:
            _html = f"""{obj.status}"""
        except Exception:
            logging.warning(traceback.format_exc())

        return Markup(_html)

    def _display_jar_status(self, context, obj, name): # pylint: disable=no-self-use, unused-argument

        _html = ''
        if hasattr(obj, 'jars'):

            jars = obj.jars

            jar_status_list = [j.status for j in jars]
            jar_statuses = [(s, jar_status_list.count(s)) for s in set(jar_status_list)]
            jar_statuses = sorted(jar_statuses, key=lambda x: x[1])

            link = f"/jar/?sort=1&flt0_order_order_order_nr_equals={getattr(obj, 'order_nr')}"
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

    column_formatters = Base_ModelView.column_formatters.copy()
    column_formatters.update({
        'status': _display_status,
        'can status': _display_jar_status,
        'can position': _display_jar_position,
    })

    # Need this so the filter options are always up-to-date
    @flask_admin.expose('/')
    def index_view(self):
        self._refresh_filters_cache()
        return super().index_view()

class DocumentModelView(Base_ModelView):

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


class MainAdminView(flask_admin.AdminIndexView):

    def __init__(self, db, *args, **kwargs):

        self.db = db

        super().__init__(*args, **kwargs)

    @flask_admin.expose("/")
    @flask_admin.expose("/home")
    @flask_admin.expose("/index")
    def index(self, ):
        template = "/admin/index.html"

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
            'language_map': LANGUAGE_MAP,
        }

        return self.render(template, **ctx)

    @flask_admin.expose("/system_management")
    def system_management(self, ):
        template = "/admin/system_management.html"

        links = []
        for i, item in enumerate(SETTINGS.MACHINE_HEAD_IPADD_PORTS_LIST):
            if item:
                ip, _, ph = item
                l = Markup('<a href="http://{}:{}/admin" > HEAD {} admin </a>'.format(ip, ph, i))
                links.append(l)

        logging.warning(f"request.host:{request.host}")
        ctx = {
            'ws_ip_addr_and_port': "{}:{}".format(request.host.split(':')[0], 13000),
            'alfa40_admin_url': "http://{}:{}/admin".format(request.host.split(':')[0], 8080),
            'current_language': SETTINGS.LANGUAGE,
            'language_map': LANGUAGE_MAP,
        }

        return self.render(template, **ctx)

def init_admin(app, db):

    main_view_ = MainAdminView(db, url='/')

    admin_ = flask_admin.base.Admin(app, name=_gettext('Alfa_CRX'), template_mode='bootstrap3', index_view=main_view_)

    admin_.add_view(OrderModelView(Order, db.session))
    admin_.add_view(JarModelView(Jar, db.session, "Can"))
    admin_.add_view(EventModelView(Event, db.session))
    admin_.add_view(DocumentModelView(Document, db.session))

    admin_.add_link(MenuLink(name='System Management', category='', url='/system_management'))

    return admin_

