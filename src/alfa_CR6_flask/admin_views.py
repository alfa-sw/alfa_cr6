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
import csv

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
from base64 import urlsafe_b64encode, urlsafe_b64decode
from http import HTTPStatus
from shutil import make_archive

from flask import (Markup, redirect, flash, request, send_file, current_app)  # pylint: disable=import-error

import flask_admin  # pylint: disable=import-error
from flask_admin.contrib.sqla import ModelView  # pylint: disable=import-error
from flask_admin.contrib.sqla.filters import FilterInList, FilterNotInList  # pylint: disable=import-error
from flask_admin.actions import action  # pylint: disable=import-error

from alfa_CR6_backend.models import Jar, Order, Event, compile_barcode
from alfa_CR6_backend.globals import (LANGUAGE_MAP, import_settings, get_alfa_serialnumber, tr_)
from alfa_CR6_backend.order_parser import OrderParser
from alfa_CR6_backend.sw_xml_can_output import SwXmlCanOutput

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

    max_rec_lev = 4
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

def _reformat_head_events_to_csv(temp_pth, db_session):

    logging.info(f"db_session:{db_session}")

    f_name = os.path.join(temp_pth, "head_events.csv")
    with open(f_name, 'w', newline='', encoding='UTF-8') as csvfile:
        _writer = csv.writer(
            csvfile, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)

        _header = ['error_code', 'error_message', 'head name', 'date_created']
        _keys = ['severity', 'description', 'source', 'date_created']

        _writer.writerow(_header)
        for e in db_session.query(Event).filter(Event.name == "HEAD").all():
            item = e.object_to_dict()
            _writer.writerow([item.get(k, '') for k in _keys])

    return f_name

def _generate_json_complete_filename(formula_name, extension, formula_step=None):
    if extension != "json":
        raise ValueError(f'Found wrong Json extension: "{extension}"')

    formula_name = formula_name.replace("/", "_")

    if formula_step:
        fstep_str = str(formula_step)
        if not fstep_str.isdigit():
            raise ValueError(f'Step {formula_step} must be a digit!')
        formula_name = f"{formula_name}_step{fstep_str}"

    base_path = SETTINGS.WEBENGINE_DOWNLOAD_PATH.strip()
    complete_name = f'{formula_name}.{extension}'

    if os.path.exists(os.path.join(base_path, complete_name)):
        i = 1
        while True:
            new_filename = f"{formula_name} ({i}).{extension}"

            if not os.path.exists(os.path.join(base_path, new_filename)):
                complete_name = new_filename
                break
            i += 1

    return complete_name

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

    def __init__(self, *args, **kwargs):

        logging.warning(f"args:{args} kwargs:{kwargs}")

        super().__init__(*args, **kwargs)

        logging.warning(f"self.session:{self.session}")

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

    @action('download_xml', tr_('Download XML'), tr_('Download XML data for selected cans?'))
    def action_download_xml(self, ids):  # pylint: disable=(too-many-locals

        ret = None
        pth_ = os.path.join(SETTINGS.TMP_PATH, "xml")

        try:
            if not os.path.exists(pth_):
                os.makedirs(pth_)

            subprocess.run(f"rm -f {pth_}/*", check=False, shell=True)

            query = self.session.query(Jar).filter(Jar.id.in_(ids))

            count = 0
            for j in query.all():
                q_ = self.session.query(Order).filter(Order.id == j.order_id)
                o = q_.first()
                c = SwXmlCanOutput(j, o)
                c.parse()
                c.to_xml()
                out_file_name = str(compile_barcode(o.order_nr, j.index)) + ".xml"
                out_file_pth = os.path.join(pth_, out_file_name)
                with open(out_file_pth, 'w', encoding='UTF-16') as fd:
                    fd.write(c.to_xml())

                    count += 1

            flash(tr_('{} cans were successfully converted.').format(count))

            if count > 1:
                alfa_serialnumber = get_alfa_serialnumber()
                timestamp_ = datetime.datetime.now().isoformat(timespec='seconds')
                xml_xfer_zip_pth = os.path.join(SETTINGS.TMP_PATH, "xml_xfer.zip")
                subprocess.run(f"rm -f {xml_xfer_zip_pth}", check=False, shell=True)
                zip_from_dir(dest_path=xml_xfer_zip_pth, source_dir=pth_, exclude_patterns=(""), mode="a")
                out_file_pth = xml_xfer_zip_pth
                out_file_name = f'{alfa_serialnumber}_{timestamp_}_{os.path.basename(out_file_pth)}'

            logging.warning(f"out_file_name:{out_file_name}, out_file_pth:{out_file_pth}")

            if out_file_name and out_file_pth:

                try:  # API Changed in version 2.0
                    ret = send_file(
                        out_file_pth,
                        mimetype='application/octet-stream',
                        as_attachment=True,
                        attachment_filename=out_file_name
                    )
                except Exception:  # pylint: disable=broad-except
                    ret = send_file(
                        out_file_pth,
                        mimetype='application/octet-stream',
                        as_attachment=True,
                        download_name=out_file_name
                    )

        except Exception as ex:
            logging.error(traceback.format_exc())
            flash(tr_('Failed to download XML. {}').format(str(ex)), 'error')

        return ret



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


class AdminIndexView(flask_admin.AdminIndexView):

    def __init__(self, db, *args, **kwargs):

        self.db = db

        super().__init__(*args, **kwargs)

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

        def get_refill_choices():
            if os.getenv("IN_DOCKER", False) in ['1', 'true']:
                us = SETTINGS.USER_SETTINGS
                return us.get('POPUP_REFILL_CHOICES', [])
            else:
                return getattr(SETTINGS, 'POPUP_REFILL_CHOICES', [])

        ctx = {
            'links': links,
            'ws_ip_addr_and_port': "{}:{}".format(request.host.split(':')[0], 13000),
            'alfa40_admin_url': "http://{}:{}/admin".format(request.host.split(':')[0], 8080),
            'current_language': SETTINGS.LANGUAGE,
            'language_map': LANGUAGE_MAP,
            'in_docker': os.getenv("IN_DOCKER", False) in ['1', 'true'],
            'refill_choices': get_refill_choices()
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
                colorcode_ = colorcode_.replace("/", "-")
                brand_ = formula.get('meta', {}).get('brand', '')
                brand_ = brand_.replace("/", "-")
                colorname_ = formula.get('meta', {}).get('colorName', '')

                fname_ = f"{brand_}_{colorcode_}"
                if (not brand_ and not colorcode_) and colorname_:
                    fname_ = f"{colorname_}"

                fstep = formula.get('meta', {}).get('step', '')
                fextension = 'json'
                base_path = SETTINGS.WEBENGINE_DOWNLOAD_PATH.strip()
                complete_name = _generate_json_complete_filename(fname_, fextension, fstep)
                pth_ = os.path.join(base_path, complete_name)
                logging.warning(f"pth_:{pth_}")
                with open(pth_, 'w', encoding='UTF-8') as f:

                    json.dump(formula, f, indent=2, ensure_ascii=False)

                    response_status = HTTPStatus.OK
                    response_data['result'] = "json formula saved."
                    response_data['file_name'] = f"{complete_name}"
                    response_data['batchid'] = batchid_

            elif formula.get("header") == "AkzoNobel Azure InstrumentCloud":
                OrderParser.parse_akzo_azure_json(formula.copy())

                name = formula.get('mix', {}).get('name', '')
                product_name = formula.get('mix', {}).get('productName', '')

                fname_ = f"{product_name}_{name}"
                fextension = 'json'
                base_path = SETTINGS.WEBENGINE_DOWNLOAD_PATH.strip()
                complete_name = _generate_json_complete_filename(fname_, fextension)
                pth_ = os.path.join(base_path, complete_name)
                logging.warning(f"pth_:{pth_}")
                with open(pth_, 'w', encoding='UTF-8') as f:

                    json.dump(formula, f, indent=2, ensure_ascii=False)

                    response_status = HTTPStatus.OK
                    response_data['result'] = "json formula saved."
                    response_data['file_name'] = f"{complete_name}"
                    response_data['id'] = formula.get('id')

            else:
                logging.error(f"invalid header {formula.get('header')} for received formula")

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
            answer_type = request.form.get('answer_type')
            logging.warning(f":{answer_type}")

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

        if answer_type == 'html':
            ret = redirect('/index')
            if _msgs:
                flash(Markup("<br/>".join(_msgs)))
            logging.warning("_msgs:{}".format(_msgs))

        else:
            ret = current_app.response_class(
                json.dumps({'msg': _msgs}, ensure_ascii=False),
                status=_status, content_type='application/json; charset=utf-8')

        logging.warning("ret:{}".format(ret))
        return ret

    @flask_admin.expose('/upload', methods=('POST',))
    def upload(self):     # pylint: disable=no-self-use, too-many-statements

        flash_msgs = []
        try:
            if request.method == 'POST':
                for stream in request.files.getlist('file'):
                    split_ext = os.path.splitext(stream.filename)
                    logging.warning(f"stream.mimetype:{stream.mimetype}, stream.filename:{stream.filename}, split_ext:{split_ext}.")

                    _in_docker = os.getenv("IN_DOCKER", False) in ['1', 'true']
                    _snowball_err_str = "ERROR: UNABLE TO UPLOAD this type of file with current environment."

                    if "pigment_alias.json" in stream.filename.lower():

                        with open(os.path.join(SETTINGS.DATA_PATH, 'pigment_alias.json'), 'wb') as f:
                            f.write(stream.read())
                        flash_msgs.append("pigment alias overwritten. {}".format(stream.filename))

                    elif "app_settings.py" in stream.filename.lower():
                        if _in_docker:
                            flash_msgs.append(_snowball_err_str)
                        else:
                            with open(os.path.join(SETTINGS.CONF_PATH, 'app_settings.py'), 'wb') as f:
                                f.write(stream.read())
                            flash_msgs.append("app settings overwritten. {}".format(stream.filename))

                    elif "data_and_conf.zip" in stream.filename.lower():
                        if _in_docker:
                            flash_msgs.append(_snowball_err_str)
                        else:
                            temp_pth = os.path.join(SETTINGS.TMP_PATH, "data_and_conf.zip")
                            dest_pth = os.path.join(SETTINGS.CONF_PATH, "..")
                            with open(temp_pth, 'wb') as f:
                                f.write(stream.read())
                            cmd_ = f"sudo chown -R admin:admin {SETTINGS.CONF_PATH}"
                            subprocess.run(cmd_, check=False, shell=True)
                            unzip_to_dir(dest_dir=dest_pth, source_path=temp_pth)
                            subprocess.run(cmd_, check=False, shell=True)
                            flash_msgs.append(f'unzipped settings from:{stream.filename} to :{dest_pth}.')

                    elif "data.zip" in stream.filename.lower():
                        if not _in_docker:
                            flash_msgs.append(_snowball_err_str)
                        else:
                            temp_pth = os.path.join(SETTINGS.TMP_PATH, "data.zip")
                            dest_pth = os.path.join(SETTINGS.DATA_PATH)
                            with open(temp_pth, 'wb') as f:
                                f.write(stream.read())
                            unzip_to_dir(dest_dir=dest_pth, source_path=temp_pth)
                            flash_msgs.append(f'unzipped settings from:{stream.filename} to :{dest_pth}.')

                    elif split_ext[1:] and split_ext[1] == '.png':
                        dest_pth = os.path.join(SETTINGS.CUSTOM_PATH, "browser_btn.png")
                        with open(dest_pth, 'wb') as f:
                            f.write(stream.read())

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
    def download(self):     # pylint: disable=no-self-use, too-many-statements

        data_set_name = request.args.get('data_set_name', 'full_db')

        logging.warning("data_set_name:{}".format(data_set_name))

        flash_msgs = []
        file_to_send = None
        out_fname = None
        alfa_serialnumber = get_alfa_serialnumber()
        try:
            timestamp_ = datetime.datetime.now().isoformat(timespec='seconds')
            data_set_name_lower = data_set_name.lower().strip()
            logging.warning(f"data_set_name_lower({len(data_set_name_lower)}):{data_set_name_lower}.")
            if data_set_name_lower == 'full_db':
                file_to_send = SETTINGS.SQLITE_CONNECT_STRING.split('///')[1]
                out_fname = f'{alfa_serialnumber}_{timestamp_}_{os.path.basename(file_to_send)}'
            elif data_set_name_lower == 'data.zip':
                temp_pth = os.path.join(SETTINGS.TMP_PATH, "data")
                make_archive(temp_pth, 'zip', SETTINGS.DATA_PATH)
                file_to_send = f'{temp_pth}.zip'
                out_fname = f'{alfa_serialnumber}_{timestamp_}_{os.path.basename(file_to_send)}'
            elif data_set_name_lower == 'data_and_conf.zip':
                temp_pth = os.path.join(SETTINGS.TMP_PATH, "data_and_conf.zip")
                cmd_ = f"sudo chown -R admin:admin {SETTINGS.CONF_PATH}"
                subprocess.run(cmd_, check=False, shell=True)
                zip_from_dir(dest_path=temp_pth, source_dir=SETTINGS.CONF_PATH, exclude_patterns=("cache", "back", "temp"), mode="w")
                zip_from_dir(dest_path=temp_pth, source_dir=SETTINGS.DATA_PATH, exclude_patterns=("webengine", "cache", "back", "temp"), mode="a")
                subprocess.run(cmd_, check=False, shell=True)
                file_to_send = temp_pth
                out_fname = f'{alfa_serialnumber}_{timestamp_}_{os.path.basename(file_to_send)}'
            elif data_set_name_lower == 'log_and_tmp.zip':
                temp_pth = os.path.join(SETTINGS.TMP_PATH, "log_and_tmp.zip")
                zip_from_dir(dest_path=temp_pth, source_dir=SETTINGS.LOGS_PATH, exclude_patterns=[], mode="w")
                zip_from_dir(dest_path=temp_pth, source_dir=SETTINGS.TMP_PATH, exclude_patterns=("cache", "log_and_tmp", ".zip", ".whl"), mode="a")
                file_to_send = temp_pth
                out_fname = f'{alfa_serialnumber}_{timestamp_}_{os.path.basename(file_to_send)}'
            elif data_set_name_lower == 'app_settings.py':
                file_to_send = os.path.join(SETTINGS.CONF_PATH, "app_settings.py")
                out_fname = f'{alfa_serialnumber}_{timestamp_}_{os.path.basename(file_to_send)}'
            elif 'logo_image' in data_set_name_lower:
                file_to_send = os.path.join(SETTINGS.CUSTOM_PATH, "browser_btn.png")
                out_fname = f'{alfa_serialnumber}_{timestamp_}_{os.path.basename(file_to_send)}'
            elif 'last_label' in data_set_name_lower:
                file_to_send = os.path.join(SETTINGS.TMP_PATH, "tmp_file.png")
                out_fname = f'{alfa_serialnumber}_{timestamp_}_{os.path.basename(file_to_send)}'
            elif 'head_events' in data_set_name_lower:
                file_to_send = _reformat_head_events_to_csv(SETTINGS.TMP_PATH, db_session=self.db.session)
                out_fname = f'{alfa_serialnumber}_{timestamp_}_{os.path.basename(file_to_send)}'
            else:
                flash_msgs.append("unknown data_set_name: {}".format(data_set_name_lower))
        except Exception as exc:  # pylint: disable=broad-except
            flash_msgs.append('Error trying to download files: {}'.format(exc))
            logging.error(traceback.format_exc())

        if flash_msgs:
            flash(Markup("<br/>".join(flash_msgs)))

        if file_to_send and out_fname:
            logging.warning("file_to_send:{}, out_fname:{}".format(file_to_send, out_fname))

            try:  # API Changed in version 2.0
                ret = send_file(
                    file_to_send,
                    mimetype='application/octet-stream',
                    as_attachment=True,
                    attachment_filename=out_fname
                )
            except Exception:  # pylint: disable=broad-except
                ret = send_file(
                    file_to_send,
                    mimetype='application/octet-stream',
                    as_attachment=True,
                    download_name=out_fname
                )

            return ret

        logging.warning("flash_msgs:{}".format(flash_msgs))
        ret = redirect('/index')
        return ret
    @flask_admin.expose("/manual/<manual_id>")
    def manual(self, manual_id):

        template = "/manual.html"

        ctx = {'manual_id': manual_id}

        html_ = self.render(template, **ctx)
        logging.warning(f"html_:{html_}")

        return html_

    @flask_admin.expose("/manual_index")
    def manual_index(self):

        template = "/manual_index.html"

        manual_id_list = [
            (None, Markup(f"{tr_('HMI MANUAL')}")),
            ("HMI_ENG", tr_('English')),
            ("HMI_ESP", tr_('Español')),
            (None, Markup(f"{tr_('OPERATOR MANUAL')}")),
            ("Operator_IT", tr_('Italiano')),
            ("Operator_EN", tr_('English')),
            ("Operator_ES", tr_('Español')),
            ("Operator_FR", tr_('Français')),
            ("Operator_DE", tr_('Deutsch')),
            ("Operator_PL", tr_('Polish')),
            ("Operator_NL", tr_('Dutch')),
            (None, Markup(f"{tr_('TECHNICAL MANUAL')}")),
            ("Technical_EN", tr_('English')),
            ("Technical_IT", tr_('Italiano')),
            ("Technical_ES", tr_('Español')),
            ("Technical_FR", tr_('Français')),
            ("Technical_DE", tr_('Deutsch')),
            (None, Markup(f"{tr_('Maintenance')}")),
            ("Maintenance_EN", tr_('English')),
            ("Maintenance_DE", tr_('Deutsch')),
            ("Maintenance_ES", tr_('Español')),
            ("Maintenance_FR", tr_('Français')),
            ("Maintenance_IT", tr_('Italiano')),
        ]
        ctx = {
            'manual_id_list': manual_id_list,
            'tr_': tr_,
        }

        html_ = self.render(template, **ctx)
        # ~ logging.warning(f"html_:{html_}")

        return html_

    @flask_admin.expose("/troubleshooting/<error_code>")
    def troubleshooting(self, error_code):

        template = "/troubleshooting.html"

        here = os.path.dirname(os.path.abspath(__file__))
        dir_path = os.path.join(here, "static", "troubleshooting", f"Errore.{error_code}")

        if os.path.exists(dir_path):
            dir_list = sorted(os.listdir(dir_path))

            image_file_list = [f"/static/troubleshooting/Errore.{error_code}/{f}" for f in dir_list]

            ctx = {
                'error_code': error_code,
                'image_file_list': image_file_list,
                'header': tr_('Error:{}').format(error_code),
            }

        else:

            ctx = {
                'error_directory_not_found': tr_('troubleshooting instructions are missing for error:{}').format(error_code),
            }

        html_ = self.render(template, **ctx)

        return html_
