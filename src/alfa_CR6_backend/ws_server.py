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

from jinja2 import Environment, FileSystemLoader

import websockets  # pylint: disable=import-error

from flask import Markup # pylint: disable=import-error

from alfa_CR6_backend.globals import (get_version, set_language, import_settings, get_application_instance, tr_)

here_ = os.path.dirname(os.path.abspath(__file__))
pth_ = os.path.join(here_, "templates/")
JINJA_ENVIRONMENT = Environment(loader=FileSystemLoader(pth_ ))

class HomePage:

    async def refresh_page(self, msg_dict, websocket, parent):

        logging.warning(f"self:{self}, msg_dict:{msg_dict}, websocket:{websocket}, parent:{parent}.")

        template = JINJA_ENVIRONMENT.get_template("home_page.html")
        html_ = template.render()
        logging.warning(f"html_:{html_}.")

        msg = json.dumps({
            'type': 'html',
            'target': 'home_page',
            'value': html_,
        })
        await websocket.send(msg)

    async def click(self, msg_dict, websocket, parent):

        logging.warning(f"self:{self}, msg_dict:{msg_dict}, websocket:{websocket}, parent:{parent}.")


class MenuPage:

    async def refresh_page(self, msg_dict, websocket, parent):

        logging.warning(f"self:{self}, msg_dict:{msg_dict}, websocket:{websocket}, parent:{parent}.")

    async def click(self, msg_dict, websocket, parent):

        logging.warning(f"self:{self}, msg_dict:{msg_dict}, websocket:{websocket}, parent:{parent}.")


class RemoteUiMessageHandler: # pylint: disable=too-few-public-methods

    pages = {
        'home_page': HomePage(),
        'menu_page': MenuPage(),
    }

    @classmethod
    async def handle_msg(cls, msg, websocket, parent):

        # ~ logging.warning(f"websocket:{websocket}, msg:{msg}.")
        try:
            msg_dict = json.loads(msg)
            logging.warning(f"msg_dict:{msg_dict}.")
            event = msg_dict.get('event')
            page_id = msg_dict.get('page_id')

            handler = getattr(cls.pages.get(page_id), event)
            if handler:
                ret = await handler(msg_dict, websocket, parent)
                logging.warning(f"ret:{ret}.")

        except Exception:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())

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

            msg_dict = json.loads(msg)

            if msg_dict.get("command"):

                if msg_dict["command"] == "change_language":
                    await cls.__change_language(msg_dict)
                elif msg_dict["command"] == "ask_settings":
                    await cls.__ask_settings(websocket)
                elif msg_dict["command"] == "ask_formula_files":
                    await cls.__ask_formula_files(websocket)
                elif msg_dict["command"] == "ask_platform_info":
                    await cls.__ask_platform_info(msg_dict, websocket)
                elif msg_dict["command"] == "ask_temperature_logs":
                    await cls.__ask_temperature_logs(msg_dict, websocket)
                elif msg_dict["command"] == "create_order_from_file":
                    await cls.__create_order_from_file(msg_dict, websocket)
            elif msg_dict.get("debug_command"):

                try:
                    cmd_ = msg_dict["debug_command"]
                    ret = eval(cmd_)     # pylint: disable=eval-used
                except Exception as e:   # pylint: disable=broad-except
                    ret = str(e)
                answer = json.dumps({
                    'type': 'debug_answer',
                    'value': html.escape(str(ret)),
                })
                await websocket.send(answer)
                logging.warning(f"answer:{answer}")

        except Exception:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())

    @classmethod
    async def __change_language(cls, msg_dict):

        params = msg_dict.get("params", {})
        lang = params.get("lang")
        set_language(lang)

    @classmethod
    async def __ask_settings(cls, websocket):
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
    async def __create_order_from_file(cls, msg_dict, websocket):
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
    async def __ask_formula_files(cls, websocket):

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
    async def __ask_platform_info(cls, msg_dict, websocket):

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
    async def __ask_temperature_logs(cls, msg_dict, websocket):

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


class WsServer: # pylint: disable=too-many-instance-attributes

    def __init__(self, parent, ws_host, ws_port):

        self.parent = parent
        self.ws_host = ws_host
        self.ws_port = ws_port
        asyncio.ensure_future(websockets.serve(self.new_client_handler, self.ws_host, self.ws_port))

        self.ws_clients = []
        self.remote_ui_clients = []

        self.__version__ = get_version()

    def _format_to_html(self, type_, msg):

        html_ = ""
        html_ += '<div>'

        logging.debug(f"self:{self} type_:{type_}")
        logging.debug(f" msg:{msg}")

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

            for client in self.ws_clients:
                await client.send(message)

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
            for client in self.ws_clients:
                await client.send(msg_)

        except BaseException:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())

    async def new_client_handler(self, websocket, path):
        try:
            logging.warning("appending websocket:{}, path:{}.".format(websocket, path))
            if 'remote_ui' in path:
                self.remote_ui_clients.append(websocket)
                async for message in websocket:  # start listening for messages from ws client
                    await RemoteUiMessageHandler.handle_msg(message, websocket, self.parent)
            else:
                self.ws_clients.append(websocket)
                await self.__refresh_client_info()
                async for message in websocket:  # start listening for messages from ws client
                    await WsMessageHandler.handle_msg(message, websocket, self.parent)

        except websockets.exceptions.ConnectionClosedError:  # pylint: disable=broad-except
            logging.warning("")
        except BaseException:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())
        finally:
            if websocket in self.ws_clients:
                logging.warning("removing websocket:{}, path:{}.".format(websocket, path))
                self.ws_clients.remove(websocket)

    def refresh_can_list(self):

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

        t = self.broadcast_msg("live_can_list", live_can_list)
        asyncio.ensure_future(t)
