# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name
# pylint: disable=broad-except
# pylint: disable=logging-fstring-interpolation, consider-using-f-string

import os
import logging
import json
import datetime
import traceback
import subprocess

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
from base64 import urlsafe_b64encode, urlsafe_b64decode
from http import HTTPStatus

from flask import (Markup, redirect, flash, request, send_file, current_app)  # pylint: disable=import-error

import flask_admin  # pylint: disable=import-error
from flask_admin.contrib.sqla import ModelView  # pylint: disable=import-error
from flask_admin.contrib.sqla.filters import FilterInList, FilterNotInList  # pylint: disable=import-error

from alfa_CR6_backend.models import Jar
from alfa_CR6_backend.globals import (LANGUAGE_MAP, import_settings, get_alfa_serialnumber)
from alfa_CR6_backend.order_parser import OrderParser

SETTINGS = import_settings()

def scrambler(path: str, mode: ["obfuscate", "unobfuscate"]):
    try:
        modified = b''
        with open(path, 'rb') as f:
            original = f.read()
            if mode == "obfuscate":
                modified = urlsafe_b64encode(original)
            elif mode == "unobfuscate":
                modified = urlsafe_b64decode(original)
            else:
                raise Exception(f'invalid parameter mode:{mode}')
        with open(path, 'wb') as f:
            f.write(modified)
    except Exception:
        logging.error(traceback.format_exc())

def unzip_to_dir(dest_dir: str, source_path: str):

    if hasattr(SETTINGS, 'obfuscate_settings') and SETTINGS.obfuscate_settings:
        scrambler(source_path, "unobfuscate")

    with ZipFile(source_path, 'r') as zip_ref:
        logging.warning(f"zip_ref.namelist():{zip_ref.namelist()}")
        zip_ref.extractall(dest_dir)

def zip_from_dir(dest_path: str, source_dir: str, exclude_patterns: list, mode: str):

    exclude_patterns = {p.lower() for p in exclude_patterns}

    src_path = Path(source_dir)
    with ZipFile(dest_path, mode=mode, compression=ZIP_DEFLATED) as zf:
        for file in src_path.rglob('*'):
            # ~ if not exclude_pattern in file.parts:
            l1 = [p.lower() for p in file.parts]
            L_ = [[p2 for p2 in exclude_patterns if p2 in p1] for p1 in l1]
            # ~ logging.warning(f"l1:{l1}, L_:{L_}")
            if not sum(L_, []):
                zf.write(file, file.relative_to(src_path.parent))

    if hasattr(SETTINGS, 'obfuscate_settings') and SETTINGS.obfuscate_settings:
        scrambler(dest_path, "obfuscate")

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

    column_formatters = Base_ModelView.column_formatters.copy()
    column_formatters.update({
        'order': _display_order,
        'order_description': _display_order_description,
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

    def _display_status(self, context, obj, name): # pylint: disable=no-self-use, unused-argument
        _html = ''
        try:
            _html += f"""{obj.status}"""
        except Exception:
            _html = ''
            logging.warning(traceback.format_exc())

        return Markup(_html)

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

    column_formatters = Base_ModelView.column_formatters.copy()
    column_formatters.update({
        'description': _display_description,
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


class AdminIndexView(flask_admin.AdminIndexView):

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
            'language_map': LANGUAGE_MAP,
        }

        return self.render(template, **ctx)


    @flask_admin.expose('/upload_json_formula', methods=('POST',))
    def upload_json_formula(self):     # pylint: disable=no-self-use

        # ~ logging.warning(f"request:{request}")
        # ~ logging.warning(f"request.args:{request.args}")
        # ~ logging.warning(f"request.data:{request.data}")
        # ~ logging.warning(f"request.form:{request.form}")

        response_data = {}
        response_status = HTTPStatus.BAD_REQUEST

        try:
            request_data = request.data
            logging.info(f"request_data({type(request_data)}):{request_data}")
            formula = json.loads(request_data)
            logging.info(f"formula:{formula}")
            if formula.get("header") == "SW CRx formula file":

                OrderParser.parse_sw_json(formula.copy())

                # ~ timestamp_ = datetime.datetime.now().isoformat(timespec='seconds')
                # ~ jobid_ = formula.get('jobId', '')
                batchid_ = formula.get('batchId', '')
                colorcode_ = formula.get('meta', {}).get('colorCode', '')
                brand_ = formula.get('meta', {}).get('brand', '')
                fname_ = f"{brand_}_{colorcode_}"
                pth_ = os.path.join(SETTINGS.WEBENGINE_DOWNLOAD_PATH.strip(), fname_)
                logging.warning(f"pth_:{pth_}")
                with open(pth_, 'w', encoding='UTF-8') as f:

                    json.dump(formula, f, indent=2, ensure_ascii=False)

                    response_status = HTTPStatus.OK
                    response_data['result'] = "json formula saved."
                    response_data['file_name'] = f"{fname_}"
                    response_data['batchid'] = batchid_

        except Exception as exc:  # pylint: disable=broad-except
            response_status = HTTPStatus.UNPROCESSABLE_ENTITY
            response_data['error'] = f'Error in validating formula. {exc}'
            response_data['description'] = traceback.format_exc()
            logging.error(traceback.format_exc())

        ret = current_app.response_class(
            json.dumps({'data': response_data}, ensure_ascii=False),
            status=response_status, content_type='application/json; charset=utf-8')

        logging.warning("ret:{}".format(ret))
        return ret

    @flask_admin.expose('/upload_formula_file', methods=('POST',))
    def upload_formula_file(self):     # pylint: disable=no-self-use
        _msgs = []
        _status = HTTPStatus.BAD_REQUEST
        try:
            for stream in request.files.getlist('file'):
                logging.warning(f"stream.mimetype:{stream.mimetype}, stream.filename:{stream.filename}.")
                pth_ = os.path.join(SETTINGS.WEBENGINE_DOWNLOAD_PATH.strip(), stream.filename)
                with open(pth_, 'wb') as f:
                    f.write(stream.read())
                _status = HTTPStatus.OK
                _msgs.append("formula file uploaded. {}".format(stream.filename))
        except Exception as exc:  # pylint: disable=broad-except
            _msgs.append('Error trying to upload formula file: {}'.format(exc))
            logging.error(traceback.format_exc())

        ret = current_app.response_class(
            json.dumps({'msg': _msgs}, ensure_ascii=False),
            status=_status, content_type='application/json; charset=utf-8')
        logging.warning("ret:{}".format(ret))
        return ret

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

                    elif "data_and_conf.zip" in stream.filename.lower():
                        temp_pth = os.path.join(SETTINGS.TMP_PATH, "data_and_conf.zip")
                        dest_pth = os.path.join(SETTINGS.CONF_PATH, "..")
                        with open(temp_pth, 'wb') as f:
                            f.write(stream.read())
                        cmd_ = f"sudo chown -R admin:admin {SETTINGS.CONF_PATH}"
                        subprocess.run(cmd_, check=False, shell=True)
                        unzip_to_dir(dest_dir=dest_pth, source_path=temp_pth)
                        subprocess.run(cmd_, check=False, shell=True)
                        flash_msgs.append(f'unzipped settings from:{stream.filename} to :{dest_pth}.')

                    elif split_ext[1:] and split_ext[1] == '.sqlite':
                        orig_pth = SETTINGS.SQLITE_CONNECT_STRING.split('///')[1]
                        logging.warning("orig_pth:{}".format(orig_pth))
                        # ~ if os.path.split(orig_pth)[1] in os.path.split(stream.filename)[1]:
                        if 'cr' in stream.filename.lower():
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

        logging.warning("data_set_name:{}".format(data_set_name))

        flash_msgs = []
        file_to_send = None
        out_fname = None
        alfa_serialnumber = get_alfa_serialnumber()
        try:
            timestamp_ = datetime.datetime.now().isoformat(timespec='seconds')
            if data_set_name.lower() == 'full_db':
                file_to_send = SETTINGS.SQLITE_CONNECT_STRING.split('///')[1]
                out_fname = f'{alfa_serialnumber}_{timestamp_}_{os.path.basename(file_to_send)}'
            elif data_set_name.lower() == 'data_and_conf.zip':
                temp_pth = os.path.join(SETTINGS.TMP_PATH, "data_and_conf.zip")
                cmd_ = f"sudo chown -R admin:admin {SETTINGS.CONF_PATH}"
                subprocess.run(cmd_, check=False, shell=True)
                zip_from_dir(dest_path=temp_pth, source_dir=SETTINGS.CONF_PATH, exclude_patterns=("cache", "back", "temp"), mode="w")
                zip_from_dir(dest_path=temp_pth, source_dir=SETTINGS.DATA_PATH, exclude_patterns=("webengine", "cache", "back", "temp"), mode="a")
                subprocess.run(cmd_, check=False, shell=True)
                file_to_send = temp_pth
                out_fname = f'{alfa_serialnumber}_{timestamp_}_{os.path.basename(file_to_send)}'
            elif data_set_name.lower() == 'log_and_tmp.zip':
                temp_pth = os.path.join(SETTINGS.TMP_PATH, "log_and_tmp.zip")
                zip_from_dir(dest_path=temp_pth, source_dir=SETTINGS.LOGS_PATH, exclude_patterns=[], mode="w")
                zip_from_dir(dest_path=temp_pth, source_dir=SETTINGS.TMP_PATH, exclude_patterns=("cache", "log_and_tmp", ".zip", ".whl"), mode="a")
                file_to_send = temp_pth
                out_fname = f'{alfa_serialnumber}_{timestamp_}_{os.path.basename(file_to_send)}'
            elif data_set_name.lower() == 'app_settings.py':
                file_to_send = os.path.join(SETTINGS.CONF_PATH, "app_settings.py")
                out_fname = f'{alfa_serialnumber}_{timestamp_}_{os.path.basename(file_to_send)}'
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
