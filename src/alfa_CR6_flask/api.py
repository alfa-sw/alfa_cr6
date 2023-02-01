# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name
# pylint: disable=broad-except
# pylint: disable=logging-fstring-interpolation, consider-using-f-string

import os
import logging
import traceback
import json
import subprocess
import csv
import datetime

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
from base64 import urlsafe_b64encode, urlsafe_b64decode

from http import HTTPStatus

from flask import (Markup, redirect, flash, request, send_file, current_app)  # pylint: disable=import-error

from flask_restful import Resource, Api  # pylint: disable=import-error

# ~ from flask_restless_swagger import SwagAPIManager as APIManager  # pylint: disable=import-error, import-outside-toplevel
from flask_restless import APIManager  # pylint: disable=import-error, import-outside-toplevel
from flask_restless.serialization import DefaultSerializer, DefaultDeserializer  # pylint: disable=import-error, import-outside-toplevel

from alfa_CR6_backend.models import (Order, Jar, Event, Document)
from alfa_CR6_backend.globals import (import_settings, get_alfa_serialnumber)
from alfa_CR6_backend.order_parser import OrderParser


URL_PREFIX = '/api/v1'

SETTINGS = import_settings()

def init_ad_hoc_api(app, db):  # pylint: disable=too-many-statements

    logging.warning(f"app:{app}, db:{db}")

    def _scrambler(path: str, mode: ["obfuscate", "unobfuscate"]):
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

    def _unzip_to_dir(dest_dir: str, source_path: str):

        if hasattr(SETTINGS, 'obfuscate_settings') and SETTINGS.obfuscate_settings:
            _scrambler(source_path, "unobfuscate")

        with ZipFile(source_path, 'r') as zip_ref:
            logging.warning(f"zip_ref.namelist():{zip_ref.namelist()}")
            zip_ref.extractall(dest_dir)

    def _zip_from_dir(dest_path: str, source_dir: str, exclude_patterns: list, mode: str):

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
            _scrambler(dest_path, "obfuscate")

    def _reformat_head_events_to_csv(temp_pth, db_session):

        logging.info(f"db_session:{db_session}")

        f_name = os.path.join(temp_pth, "head_events.csv")
        with open(f_name, 'w', newline='', encoding='UTF-8') as csvfile:
            _writer = csv.writer(
                csvfile, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)

            _header = ['error_code', 'error_message', 'head name', 'date_created']
            _keys = ['severity', 'description', 'name', 'date_created']

            _writer.writerow(_header)
            for e in db_session.query(Event).filter(Event.name == "HEAD").all():
                item = e.object_to_dict()
                _writer.writerow([item.get(k, '') for k in _keys])

        return f_name

    @app.route('/upload_formula_file', methods=('POST',))
    def upload_formula_file():
        flash_msgs = []
        response_status = HTTPStatus.BAD_REQUEST
        try:
            answer_type = request.form.get('answer_type')
            redirect_to = request.form.get('redirect_to')
            logging.warning(f"{answer_type}, {redirect_to}")

            for stream in request.files.getlist('file'):
                logging.warning(f"stream.mimetype:{stream.mimetype}, stream.filename:{stream.filename}.")
                pth_ = os.path.join(SETTINGS.WEBENGINE_DOWNLOAD_PATH.strip(), stream.filename)
                with open(pth_, 'wb') as f:
                    f.write(stream.read())
                response_status = HTTPStatus.OK
                flash_msgs.append("formula file uploaded. {}".format(stream.filename))
        except Exception as exc:  # pylint: disable=broad-except
            flash_msgs.append('Error trying to upload formula file: {}'.format(exc))
            logging.error(traceback.format_exc())

        if answer_type == 'html':
            ret = redirect(redirect_to)
            if flash_msgs:
                flash(Markup("<br/>".join(flash_msgs)))
            logging.warning("flash_msgs:{}".format(flash_msgs))

        else:
            ret = current_app.response_class(
                json.dumps({'msg': flash_msgs}, ensure_ascii=False),
                status=response_status, content_type='application/json; charset=utf-8')

        logging.warning("ret:{}".format(ret))
        return ret


    @app.route('/upload_json_formula', methods=('POST',))
    def upload_json_formula():

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
                fname_ = f"{brand_}_{colorcode_}.json"
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

    @app.route('/upload', methods=('POST',))
    def upload():     # pylint: disable=too-many-statements, too-many-branches

        flash_msgs = []
        response_status = HTTPStatus.BAD_REQUEST
        try:
            answer_type = request.form.get('answer_type')
            redirect_to = request.form.get('redirect_to')
            logging.warning(f"{answer_type}, {redirect_to}")

            for stream in request.files.getlist('file'):
                split_ext = os.path.splitext(stream.filename)
                logging.warning(f"stream.mimetype:{stream.mimetype}, stream.filename:{stream.filename}, split_ext:{split_ext}.")

                if "pigment_alias.json" in stream.filename.lower():

                    with open(os.path.join(SETTINGS.DATA_PATH, 'pigment_alias.json'), 'wb') as f:
                        f.write(stream.read())
                    flash_msgs.append("pigment alias overwritten. {}".format(stream.filename))

                elif "app_settings.py" in stream.filename.lower():
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
                    _unzip_to_dir(dest_dir=dest_pth, source_path=temp_pth)
                    subprocess.run(cmd_, check=False, shell=True)
                    flash_msgs.append(f'unzipped settings from:{stream.filename} to :{dest_pth}.')

                elif split_ext[1:] and split_ext[1] == '.png':
                    dest_pth = os.path.join(SETTINGS.CUSTOM_PATH, "browser_btn.png")
                    with open(dest_pth, 'wb') as f:
                        f.write(stream.read())
                    flash_msgs.append('uploaded new logo image: {}.'.format(stream.filename))

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

            response_status = HTTPStatus.OK

        except Exception as exc:  # pylint: disable=broad-except
            flash_msgs.append('Error trying to upload files: {}'.format(exc))
            logging.error(traceback.format_exc())

        if answer_type == 'html':
            ret = redirect(redirect_to)
            if flash_msgs:
                flash(Markup("<br/>".join(flash_msgs)))
            logging.warning("flash_msgs:{}".format(flash_msgs))

        else:
            ret = current_app.response_class(
                json.dumps({'msg': flash_msgs}, ensure_ascii=False),
                status=response_status, content_type='application/json; charset=utf-8')

        logging.warning("ret:{}".format(ret))
        return ret

    @app.route('/download/<data_set_name>', methods=('GET',))
    def download(data_set_name):     # pylint: disable=too-many-statements, too-many-branches

        flash_msgs = []
        response_status = HTTPStatus.BAD_REQUEST
        try:
            # ~ data_set_name = request.args.get('data_set_name', 'full_db')
            answer_type = request.form.get('answer_type', 'html')
            redirect_to = request.form.get('redirect_to', '/index')

            logging.warning("data_set_name:{}".format(data_set_name))

            file_to_send = None
            out_fname = None
            alfa_serialnumber = get_alfa_serialnumber()
            timestamp_ = datetime.datetime.now().isoformat(timespec='seconds')
            data_set_name_lower = data_set_name.lower().strip()
            logging.warning(f"data_set_name_lower({len(data_set_name_lower)}):{data_set_name_lower}.")
            if data_set_name_lower == 'full_db':
                file_to_send = SETTINGS.SQLITE_CONNECT_STRING.split('///')[1]
                out_fname = f'{alfa_serialnumber}_{timestamp_}_{os.path.basename(file_to_send)}'
            elif data_set_name_lower == 'data_and_conf':
                temp_pth = os.path.join(SETTINGS.TMP_PATH, "data_and_conf.zip")
                cmd_ = f"sudo chown -R admin:admin {SETTINGS.CONF_PATH}"
                subprocess.run(cmd_, check=False, shell=True)
                _zip_from_dir(dest_path=temp_pth, source_dir=SETTINGS.CONF_PATH, exclude_patterns=("cache", "back", "temp"), mode="w")
                _zip_from_dir(dest_path=temp_pth, source_dir=SETTINGS.DATA_PATH, exclude_patterns=("webengine", "cache", "back", "temp"), mode="a")
                subprocess.run(cmd_, check=False, shell=True)
                file_to_send = temp_pth
                out_fname = f'{alfa_serialnumber}_{timestamp_}_{os.path.basename(file_to_send)}'
            elif data_set_name_lower == 'log_and_tmp':
                temp_pth = os.path.join(SETTINGS.TMP_PATH, "log_and_tmp.zip")
                _zip_from_dir(dest_path=temp_pth, source_dir=SETTINGS.LOGS_PATH, exclude_patterns=[], mode="w")
                _zip_from_dir(dest_path=temp_pth, source_dir=SETTINGS.TMP_PATH, exclude_patterns=("cache", "log_and_tmp", ".zip", ".whl"), mode="a")
                file_to_send = temp_pth
                out_fname = f'{alfa_serialnumber}_{timestamp_}_{os.path.basename(file_to_send)}'
            elif data_set_name_lower == 'app_settings':
                file_to_send = os.path.join(SETTINGS.CONF_PATH, "app_settings.py")
                out_fname = f'{alfa_serialnumber}_{timestamp_}_{os.path.basename(file_to_send)}'
            elif data_set_name_lower == 'logo_image':
                file_to_send = os.path.join(SETTINGS.CUSTOM_PATH, "browser_btn.png")
                out_fname = f'{alfa_serialnumber}_{timestamp_}_{os.path.basename(file_to_send)}'
            elif data_set_name_lower == 'last_label':
                file_to_send = os.path.join(SETTINGS.TMP_PATH, "tmp_file.png")
                out_fname = f'{alfa_serialnumber}_{timestamp_}_{os.path.basename(file_to_send)}'
            elif data_set_name_lower == 'head_events':
                file_to_send = _reformat_head_events_to_csv(SETTINGS.TMP_PATH, db_session=db.session)
                out_fname = f'{alfa_serialnumber}_{timestamp_}_{os.path.basename(file_to_send)}'
            else:
                flash_msgs.append("unknown data_set_name: {}".format(data_set_name_lower))

            response_status = HTTPStatus.OK

        except Exception as exc:  # pylint: disable=broad-except
            flash_msgs.append('Error trying to download files: {}'.format(exc))
            logging.error(traceback.format_exc())

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

        else:

            if answer_type == 'html':
                ret = redirect(redirect_to)
                if flash_msgs:
                    flash(Markup("<br/>".join(flash_msgs)))
                logging.warning("flash_msgs:{}".format(flash_msgs))

            else:
                ret = current_app.response_class(
                    json.dumps({'msg': flash_msgs}, ensure_ascii=False),
                    status=response_status, content_type='application/json; charset=utf-8')

            logging.warning("ret:{}".format(ret))

        return ret


def init_restful_api(app, db):

    class OrderByJobId(Resource):  # pylint: disable=too-few-public-methods

        def __init__(self, db, *args, **kwargs):

            self.db = db
            super().__init__(*args, **kwargs)

        def get(self, job_id):

            logging.warning(f"self.db:{self.db},job_id:{job_id}")

            data = []
            query_ = self.db.session.query(Order).filter(Order.description == job_id)
            query_ = query_.join(Jar).filter(Jar.position != "DELETED").limit(50)

            for order in query_.all():
                data.append(order.object_to_dict(relationships=True))

            ret = {'result': 'OK', 'data': data, 'count': len(data)}

            return ret

    _api = Api(app)

    _api.add_resource(OrderByJobId, f'{URL_PREFIX}/order_by_job_id/<job_id>', resource_class_kwargs={'db': db})

    return _api


def init_restless_api(app, db):

    class CustomSerializer(DefaultSerializer): # pylint: disable=too-few-public-methods

        def serialize_attributes(self, instance, only=None):

            ret = super().serialize_attributes(instance, only)

            if ret.get('json_properties') is not None:
                try:
                    ret['json_properties'] = json.loads(ret['json_properties'])
                except Exception:
                    logging.error(traceback.format_exc())

            return ret

    class CustomDeserializer(DefaultDeserializer): # pylint: disable=too-few-public-methods

        def __init__(self, session, model, api_manager):

            # ~ logging.warning(f"only:{only}, instance:{instance}"[:140])

            self.model_class = model
            super().__init__(session, model, api_manager)

        def deserialize(self, document):

            logging.warning(f"document:{document}"[:140])
            return self.model_class.object_from_dict(document)

    class CustomAPIManager(APIManager): # pylint: disable=too-few-public-methods

        EXCLUDE_COLUMNS_MAP = {
            # ~ 'order': ['jars'],
            # ~ 'jar': ['json_properties'],
        }

        @staticmethod
        def _universal_GET_preprocessor(*args, **kwargs):
            logging.warning(f"args:{args}, kwargs:{kwargs}"[:200])

        @staticmethod
        def _universal_GET_postprocessor(*args, **kwargs):
            logging.warning(f"args:{args}, kwargs:{kwargs}"[:200])

        @staticmethod
        def _universal_POST_preprocessor(*args, **kwargs):
            logging.warning(f"args:{args}, kwargs:{kwargs}"[:200])

        @staticmethod
        def _universal_POST_postprocessor(*args, **kwargs):
            logging.warning(f"args:{args}, kwargs:{kwargs}"[:200])

        def __init__(self, *args, **kwargs):

            super().__init__(
                preprocessors=dict(
                    GET_RESOURCE=[self._universal_GET_preprocessor],
                    GET_COLLECTION=[self._universal_GET_preprocessor],
                    POST_RESOURCE=[self._universal_POST_preprocessor]),
                postprocessors=dict(
                    GET_RESOURCE=[self._universal_GET_postprocessor],
                    GET_COLLECTION=[self._universal_GET_postprocessor],
                    POST_RESOURCE=[self._universal_POST_postprocessor]),
                *args,
                **kwargs)

            # ~ logging.warning(f"self.preprocessors:{self.preprocessors}, self.postprocessors:{self.postprocessors}")

            for model_class, model_name, primary_key in (
                (Order, 'order', 'id'),
                (Jar, 'can', 'id'),
                (Event, 'event', 'id'),
                (Document, 'document', 'id')
            ):
                # ~ attributes = set(inspect(model_class).mapper.columns.keys())
                # ~ relationships = set(inspect(model_class).mapper.relationships.keys())

                ser_ = CustomSerializer(model_class, model_name, api_manager=self, primary_key='id')
                deser_ = CustomDeserializer(session=db.session, model=model_class, api_manager=self)

                self.create_api(model_class,
                                url_prefix=URL_PREFIX,
                                collection_name=model_name,
                                primary_key=primary_key,
                                serializer=ser_,
                                deserializer=deser_,
                                methods=['GET', 'POST', 'DELETE'])

    manager = CustomAPIManager(app, session=db.session)

    # ~ logging.warning(f"manager:{manager}")

    return manager
