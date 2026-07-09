# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name
# pylint: disable=too-many-lines
# pylint: disable=logging-fstring-interpolation, consider-using-f-string

import os
import time
import traceback
import asyncio
import json
import html
import types
import logging

import logging.handlers

import websockets  # pylint: disable=import-error

from flask import Markup # pylint: disable=import-error

from alfa_CR6_backend.globals import (get_version, set_language, import_settings, get_application_instance, tr_, set_refill_popup_choices)
from alfa_CR6_backend.settings_manager import SettingsManager


async def _send_protocol_error(websocket, code):
    answer = json.dumps({
        'type': 'error',
        'code': code,
    })
    await websocket.send(answer)
    return answer


class WsMessageHandler: # pylint: disable=too-few-public-methods

    settings = None
    parent = None

    @classmethod
    async def handle_msg(cls, msg, websocket, parent):

        logging.warning(f"websocket:{websocket}, msg:{msg}.")

        try:

            if not cls.settings:
                cls.settings = import_settings()

            cls.parent = parent

            try:
                msg_dict = json.loads(msg)
            except json.JSONDecodeError:
                logging.warning("bad_request: invalid json payload")
                answer = await _send_protocol_error(websocket, 'bad_request')
                logging.warning(f"answer:{answer}")
                return

            if not isinstance(msg_dict, dict):
                logging.warning(
                    "bad_request: expected object payload, got:%s",
                    type(msg_dict).__name__,
                )
                answer = await _send_protocol_error(websocket, 'bad_request')
                logging.warning(f"answer:{answer}")
                return

            if msg_dict.get("command"):
                answer = None
                command = msg_dict.get("command")

                if not isinstance(command, str):
                    logging.warning("bad_request: command is not a string")
                    answer = await _send_protocol_error(websocket, 'bad_request')
                    logging.warning(f"answer:{answer}")
                    return

                if hasattr(cls, command):
                    _callable = getattr(cls, command)
                    answer = await _callable(msg_dict, websocket)
                else:
                    logging.warning("bad_request: unknown command:%s", command)
                    answer = await _send_protocol_error(websocket, 'bad_request')

                logging.warning(f"answer:{answer}")

            elif msg_dict.get("debug_command"):
                logging.warning("bad_request: debug_command disabled")
                answer = await _send_protocol_error(websocket, 'bad_request')
                logging.warning(f"[debug_command] answer:{answer}")

            else:
                logging.warning("bad_request: missing supported command field")
                answer = await _send_protocol_error(websocket, 'bad_request')
                logging.warning(f"answer:{answer}")

        except Exception:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())
            try:
                answer = await _send_protocol_error(websocket, 'internal_error')
                logging.warning(f"answer:{answer}")
            except Exception:  # pylint: disable=broad-except
                logging.error("failed sending internal_error:\n%s", traceback.format_exc())

    @classmethod
    async def change_language(cls, msg_dict, websocket): # pylint: disable=unused-argument

        params = msg_dict.get("params", {})
        lang = params.get("lang")
        set_language(lang)

    @classmethod
    async def ask_aliases(cls, msg_dict, websocket): # pylint: disable=unused-argument

        _alias_file = os.path.join(cls.settings.DATA_PATH, "pigment_alias.json")
        with open(_alias_file, encoding='UTF-8') as f:
            alias_dict = json.load(f)
        answ_ = [f"{k}: {v}" for k, v in alias_dict.items()]
        answ_.sort()
        answ_ = html.unescape('<br/>'.join(answ_))
        logging.warning(f"answ_:{answ_}.")
        answer = json.dumps({
            'type': 'ask_aliases_answer',
            'value': answ_,
        })
        await websocket.send(answer)

    @classmethod
    async def ask_settings(cls, msg_dict, websocket): # pylint: disable=unused-argument
        S = cls.settings
        s_ = [f"{i}: {getattr(S, i)}" for i in dir(S) if not i.startswith("_") and not isinstance(getattr(S, i), types.ModuleType)]

        answ_ = html.unescape('<br/>'.join(s_))
        logging.warning(f"answ_:{answ_}.")

        answer = json.dumps({
            'type': 'ask_settings_answer',
            'value': answ_,
        })
        await websocket.send(answer)

    @classmethod
    async def ask_settings_json(cls, msg_dict, websocket): # pylint: disable=unused-argument
        """Return settings as a JSON object plus origin info (docker/host)."""
        try:
            data = SettingsManager.get_editable_settings()
            origin = 'docker' if (os.getenv('IN_DOCKER', False) in ['1', 'true']) else 'host'

            # Provide filtered schema for visible keys so UI can render constraints
            properties = SettingsManager.SCHEMA.get('properties', {})
            visible_schema = {k: v for k, v in properties.items() if v.get('ui_show', True) and k in data}

            # sound_level: PER ORA la UI espone il solo 'auto' su OGNI monitor.
            # Le opzioni percentuali (volume monitor via DDC/CI) sono rimandate:
            # l'impostazione del volume alto e' sicura solo con alimentatore
            # dedicato del monitor (senza PSU il drive alto fa collassare lo
            # scaler - misurato), quindi verranno riabilitate quando il
            # requisito PSU sara' gestito. Il volume di sicurezza lo applica gia'
            # la policy host per-monitor (0x000F -> 40 via DDC).
            # Copia profonda per non mutare lo SCHEMA di classe.
            if 'REFILL_ALARM_NOTIFICATION' in visible_schema:
                import copy  # pylint: disable=import-outside-toplevel
                spec_ = copy.deepcopy(visible_schema['REFILL_ALARM_NOTIFICATION'])
                if 'sound_level' in spec_.get('properties', {}):
                    spec_['properties']['sound_level']['enum'] = ['auto']
                visible_schema['REFILL_ALARM_NOTIFICATION'] = spec_

            answer = json.dumps({
                'type': 'ask_settings_json',
                'value': data,
                'origin': origin,
                'schema': visible_schema,
            })
            await websocket.send(answer)
        except Exception:
            logging.error(traceback.format_exc())

    @classmethod
    async def save_settings(cls, msg_dict, websocket):
        """Save provided settings. Expects params.updates = {key: value}."""
        try:
            params = msg_dict.get('params', {})
            updates = params.get('updates', {}) or {}
            if not isinstance(updates, dict):
                raise ValueError('updates must be a dict')

            # Validate and apply through centralized manager
            SettingsManager.set_updates(updates)

            # force re-import on next request
            cls.settings = None

            answer = json.dumps({'type': 'save_settings_result', 'value': 'OK'})
            await websocket.send(answer)

            async def _reload_supervisor():
                try:
                    await asyncio.sleep(1.0)
                    import subprocess
                    subprocess.run(['sudo', 'supervisorctl', 'reload'], check=False)
                except Exception:
                    logging.error('Failed to reload supervisor:\n%s', traceback.format_exc())

            asyncio.create_task(_reload_supervisor())
        except Exception:
            logging.error(traceback.format_exc())
            answer = json.dumps({'type': 'save_settings_result', 'value': 'ERROR'})
            await websocket.send(answer)

    @classmethod
    async def create_order_from_file(cls, msg_dict, websocket):
        params = msg_dict.get("params", {})
        file_name = params.get("file_name")
        logging.warning(f"file_name:{file_name}.")
        try:
            _path = cls.settings.WEBENGINE_DOWNLOAD_PATH.strip()
            path_to_file = os.path.join(_path, file_name)

            get_application_instance().main_window.order_page.populate_order_table()
            order_list = get_application_instance().create_orders_from_file(path_to_file=path_to_file, n_of_jars=1, silent=True)
            get_application_instance().main_window.order_page.populate_order_table()

            order_nr_ = order_list and order_list[0] and order_list[0].order_nr
            if order_nr_:
                msg_ = tr_("<h4>created order {} from file:{}</h4>").format(order_nr_, file_name)
            else:
                msg_ = tr_("<h4>can't create order from file:{}</h4>").format(order_nr_, file_name)
        except Exception as e:  # pylint: disable=broad-except
            msg_ = tr_('<h4>ERROR:{}</h4>').format(e)

        answer = json.dumps({
            'type': 'message_display',
            'value': html.unescape(msg_),
            'make_visible': True,
        })
        await websocket.send(answer)

    @classmethod
    async def ask_formula_files(cls, msg_dict, websocket): # pylint: disable=unused-argument

        _path = cls.settings.WEBENGINE_DOWNLOAD_PATH.strip()
        s_ = [f for f in os.listdir(_path) if os.path.isfile(os.path.join(_path, f))]

        if s_:
            val_ = tr_("create order")
            answ_ = [f"""<input type="button" onclick="create_order_from_file('{s}');" value="{val_}"></input> {s} """ for s in s_]
            answ_ = html.unescape('<br/>'.join(answ_))
        else:
            answ_ = tr_("no formula file present")
        logging.warning(f"answ_:{answ_}.")

        answer = json.dumps({
            'type': 'ask_formula_files_answer',
            'value': answ_,
        })
        await websocket.send(answer)

    @classmethod
    async def ask_platform_info(cls, msg_dict, websocket):

        params = msg_dict.get("params", {})
        head_letter = params.get("head_letter")
        m = cls.parent.get_machine_head_by_letter(head_letter)

        path = "admin/platform?cmd=info"
        method = "GET"
        data = {}
        ret = await m.call_api_rest(path, method, data, timeout=30, expected_ret_type='html')
        title = f'<b> head:{head_letter} platform info:</b> <a href="#">[back to top]</a>'

        answer = json.dumps({
            'type': 'ask_platform_answer',
            'value': title + html.unescape(ret),
        })
        await websocket.send(answer)

    @classmethod
    async def ask_temperature_logs(cls, msg_dict, websocket):

        params = msg_dict.get("params", {})
        head_letter = params.get("head_letter")
        m = cls.parent.get_machine_head_by_letter(head_letter)

        path = "admin/platform?cmd=temperature_logs"
        method = "GET"
        data = {}
        ret = await m.call_api_rest(path, method, data, timeout=30, expected_ret_type='json')
        html_ = f'<b> head:{head_letter} temperature logs:</b> <a href="#">[back to top]</a><br/>'
        html_ += "<br/>".join(ret)

        answer = json.dumps({
            'type': 'ask_platform_answer',
            'value': html.unescape(html_),
        })
        await websocket.send(answer)

    @classmethod
    async def change_refill_popup_choices(cls, msg_dict, websocket):
        params = msg_dict.get("params", {})
        refill_choices = params.get("refill_choices")
        set_refill_popup_choices(refill_choices)

class WsServer: # pylint: disable=too-many-instance-attributes

    def __init__(self, parent, ws_host, ws_port):

        self.parent = parent
        self.ws_host = ws_host
        self.ws_port = ws_port
        asyncio.ensure_future(websockets.serve(
            self.new_client_handler, self.ws_host, self.ws_port,
            ping_interval=20, ping_timeout=10, close_timeout=5,
            max_size=2**20))

        self.ws_clients = set()
        self._refresh_can_list_dirty = False
        self._refresh_can_list_task = None
        self._refresh_can_list_interval = 0.1

        self.__version__ = get_version()

    def _format_to_html(self, type_, msg):

        html_ = ""
        html_ += '<div>'

        logging.debug("self:%s type_:%s", self, type_)
        logging.debug(" msg:%s", msg)

        if type_ == "live_can_list" and isinstance(msg, list):
            for i in msg:
                # ~ html_ += "<tr><td>{}</td></tr>".format(i)
                html_ += "{}<br/>".format(i)

        elif "device:machine:status" in type_:

            if isinstance(msg, dict):
                status_list = list(msg.items())
            elif isinstance(msg, list):
                status_list = msg

            for k, v in status_list:

                if k in ('status_level',
                         'cycle_step',
                         'error_code',
                         'error_code',
                         'temperature',
                         'circuit_engaged',
                         'container_presence',
                         'error_message',
                         'timestamp',
                         'message_id',
                         'last_update'):
                    html_ += "<b>{}</b>: {}<br/>".format(k, v)

                elif k in ('photocells_status',
                           'jar_photocells_status',
                           'crx_outputs_status'):

                    val_ = int(v)
                    html_ += "<b>{}</b>: {:04b} {:04b} {:04b} | 0x{:04X}<br/>".format(
                        k, 0xF & (val_ >> 8), 0xF & (val_ >> 4), 0xF & (val_ >> 0), val_)

                else:
                    continue

        else:
            html_ += f"unknown type_:{type_} msg:{msg}<br/>"

        # ~ html_ += "</table>"
        html_ += "</div>"

        return Markup(html_)

    async def _broadcast_raw(self, message):
        async def _safe_send(client):
            try:
                await asyncio.wait_for(client.send(message), timeout=5)
            except Exception:
                self.ws_clients.discard(client)

        if self.ws_clients:
            await asyncio.gather(*[_safe_send(c) for c in set(self.ws_clients)])

    async def broadcast_msg(self, type_, msg):

        if self.ws_clients:
            message = json.dumps({
                'type': type_,
                'value': self._format_to_html(type_, msg),
                'server_time': "{} - ver.:{} - paused: {}.".format(
                    time.strftime("%Y-%m-%d %H:%M:%S (%Z)"),
                    self.__version__, get_application_instance().carousel_frozen),
            })
            # ~ logging.warning("message:{}.".format(message))

            await self._broadcast_raw(message)

        return True

    async def __refresh_client_info(self):

        try:

            for m in get_application_instance().machine_head_dict.values():
                if m:
                    await self.broadcast_msg(f'device:machine:status_{m.index}', dict(m.status))

            self.refresh_can_list()

            msg_ = json.dumps({
                'type': 'current_language_label',
                'value': self.parent.settings.LANGUAGE,
            })
            await self._broadcast_raw(msg_)

        except BaseException:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())

    async def new_client_handler(self, websocket, path):
        try:
            logging.warning("appending websocket:{}, path:{}.".format(websocket, path))
            self.ws_clients.add(websocket)
            await self.__refresh_client_info()
            async for message in websocket:  # start listening for messages from ws client
                await WsMessageHandler.handle_msg(message, websocket, self.parent)

        except websockets.exceptions.ConnectionClosed as e:  # pylint: disable=broad-except
            logging.warning("websocket connection closed: %s, path:%s", e, path)
        except BaseException:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())
        finally:
            logging.warning("removing websocket:{}, path:{}.".format(websocket, path))
            self.ws_clients.discard(websocket)

    def _build_live_can_list(self):

        live_can_list = []
        for k, j in get_application_instance().get_jar_runners().items():
            if j and j.get('jar'):
                machine_sts_lev = ''
                code_str = f"""<a href="/jar/details/?id={j.get('jar').id}">{k}</a>"""
                if j['jar'].machine_head:
                    _sts_lev = j['jar'].machine_head.status and j['jar'].machine_head.status.get("status_level")
                    machine_sts_lev = f"{j['jar'].machine_head.name}:{_sts_lev}"
                _live_can = f"{code_str} {j['jar'].status} [{j['jar'].position}, {machine_sts_lev}]"

                live_can_list.append(_live_can)

        return live_can_list

    async def _delayed_refresh_can_list(self):

        try:
            await asyncio.sleep(self._refresh_can_list_interval)

            if not self.ws_clients:
                self._refresh_can_list_dirty = False
                return

            self._refresh_can_list_dirty = False
            await self.broadcast_msg("live_can_list", self._build_live_can_list())

        except Exception:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())
        finally:
            self._refresh_can_list_task = None
            if not self.ws_clients:
                self._refresh_can_list_dirty = False
            elif self._refresh_can_list_dirty:
                self.refresh_can_list()

    def refresh_can_list(self):

        if not self.ws_clients:
            self._refresh_can_list_dirty = False
            return

        self._refresh_can_list_dirty = True
        if self._refresh_can_list_task and not self._refresh_can_list_task.done():
            return

        self._refresh_can_list_task = asyncio.ensure_future(self._delayed_refresh_can_list())
