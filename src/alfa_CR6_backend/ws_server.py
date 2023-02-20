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
import random
import logging
import logging.handlers

from jinja2 import Environment, FileSystemLoader

import websockets  # pylint: disable=import-error

from flask import Markup # pylint: disable=import-error

from alfa_CR6_backend.globals import (get_version, set_language, import_settings, get_application_instance, tr_)

here_ = os.path.dirname(os.path.abspath(__file__))
pth_ = os.path.join(here_, "templates/")

JINJA_ENVIRONMENT = Environment(loader=FileSystemLoader(pth_ ))
JINJA_ENVIRONMENT.globals['tr_'] = tr_
JINJA_ENVIRONMENT.globals['enumerate'] = enumerate

SETTINGS = import_settings()

OPEN_ALERT_DIALOG_CNTR = 0

ORDER_PAGE_COLUMNS_ORDERS = {
    'file': ["delete", "view", "create order", "file name"],
    'order': ["delete", "edit", "status", "order nr.", "file name"],
    'can': ["delete", "view", "status", "barcode"],
}
if hasattr(SETTINGS, 'ORDER_PAGE_COLUMNS_ORDERS'):
    ORDER_PAGE_COLUMNS_ORDERS.update(SETTINGS.ORDER_PAGE_COLUMNS_ORDERS)

def close_child_windows(websocket, needle_=''):

    msg = json.dumps({
        'type': 'js',
        'value': f"""close_child_windows("{needle_}");""",
    })

    t = websocket.send(msg)
    asyncio.ensure_future(t)

def open_child_window(websocket, _url, target, win_options):

    msg = json.dumps({
        'type': 'js',
        'value': f"""open_child_window("{_url}","{target}","{win_options}");""",
    })

    t = websocket.send(msg)
    asyncio.ensure_future(t)
    # ~ logging.warning("")

def open_alert_dialog(msg, websocket):

    global OPEN_ALERT_DIALOG_CNTR  # pylint: disable=global-statement

    OPEN_ALERT_DIALOG_CNTR = (OPEN_ALERT_DIALOG_CNTR + 1) % 8
    target = f"alert_win_{OPEN_ALERT_DIALOG_CNTR}"
    x = int(350 + OPEN_ALERT_DIALOG_CNTR * 20)
    y = int(150 + OPEN_ALERT_DIALOG_CNTR * 10)

    ctx = {
        'msg': msg,
        'time': time.asctime(),
        'target': target,
    }

    html_ = JINJA_ENVIRONMENT.get_template("alert_dialog.html").render(**ctx)
    # ~ logging.warning(f"html_:{html_}.")
    html_ = html_.replace('\n', '')

    win_options = f"left={x},top={y},height=320,width=520"
    msg = json.dumps({
        'type': 'js',
        'value': f"""{{open_alert_dialog("","{target}","{win_options}","{html_}");}}""",
    })

    # ~ await websocket.send(msg)
    t = websocket.send(msg)
    asyncio.ensure_future(t)
    # ~ logging.warning("")

class HomePage:

    async def refresh_head(self, parent, websocket, head_index):

        m = parent.machine_head_dict[head_index]
        status_level = m.status.get('status_level')
        msg = json.dumps({
            'type': 'html',
            'target': f"machine_status_label__{head_index}",
            'value': status_level,
        })
        await websocket.send(msg)

        open_alert_dialog(f"refresh_head() head_index:{head_index}", websocket)

    async def refresh_page(self, msg_dict, websocket, parent):

        logging.warning(f"self:{self}, msg_dict:{msg_dict}, websocket:{websocket}, parent:{parent}.")

        _machine_head_list = [(k, v) for k, v in parent.machine_head_dict.items() if v]
        n_of_heads = len(_machine_head_list)

        logging.warning(f"parent.machine_head_dict:{parent.machine_head_dict}, n_of_heads:{n_of_heads}.")

        if n_of_heads == 6:
            background_image = '/static/remote_ui/images/sinottico_6.png'
            x, w, y, h = [ int(100*i/1840) for i in (504, 378)] + [ int(100*i/960) for i in (86, 378)]
            u = '%'
        elif n_of_heads == 4:
            background_image = '/static/remote_ui/images/sinottico_4.png'
            x, w, y, h = 312, 386, 86, 382
            u = 'px'

        def style(n):
            return f"position:absolute;top:{y+(n%2)*h}{u};height:{h}{u};left:{x+(n//2)*w}{u};width:{w}{u};border:2px solid #73AD21;"

        logo_image = '/static/remote_ui/images/alfa_logo.png'

        machine_head_list = [(n, i, style(n)) for n, i in enumerate(_machine_head_list)]

        ctx = {
            'machine_head_list': machine_head_list,
            'background_image': background_image,
            'logo_image': logo_image,
        }

        html_ = JINJA_ENVIRONMENT.get_template("home_page.html").render(**ctx)
        # ~ logging.warning(f"html_:{html_}.")
        msg = json.dumps({
            'type': 'html',
            'target': 'home_page',
            'value': html_,
        })
        await websocket.send(msg)

    async def click(self, msg_dict, websocket, parent):

        logging.warning(f"self:{self}, msg_dict:{msg_dict}, websocket:{websocket}, parent:{parent}.")
        el_id = msg_dict.get('el_id') # 'machine_tank_label__2'

        if 'machine_status_label' in el_id:
            # ~ msg_dict:{'event': 'click', 'page_id': 'home_page', 'el_id': 'machine_status_label__1'}
            toks = el_id.split("__")
            if toks[1:]:
                head_index = int(toks[1])
                m = parent.machine_head_dict[head_index]
                _url = f"http://{m.ip_add}:{m.http_port}/admin"
                target = "childHeadWindow"
                win_options = "popup=1,left=0,top=0,height=916,width=1980,status=yes,toolbar=no,menubar=no,location=no"
                open_child_window(websocket, _url, target, win_options)

        elif 'machine_reserve_label' in el_id:

            i = random.randint(1, 100000)
            html_ = f""" <span style='color:red;'><h2>ALERT MESSAGE {i}</h2></span>"""
            open_alert_dialog(msg=html_, websocket=websocket)

        elif 'machine_tank_label' in el_id:

            if random.random() > 0.5:
                bg_img = 'url("/static/remote_ui/images/tank_gray.png")'
            else:
                bg_img = 'url("/static/remote_ui/images/tank_green.png")'

            msg = json.dumps({
                'type': 'css',
                'target': el_id,
                'value': {"background-image": bg_img},
            })
            await websocket.send(msg)

        # ~ _url = "http://127.0.0.1:8080/admin"
        # ~ target = "childBrowserWin"
        # ~ win_options = "popup=1,left=4,top=-10,height=900,width=1900,status=yes,toolbar=no,menubar=no,location=no"
        # ~ msg = json.dumps({
            # ~ 'type': 'js',
            # ~ 'value': f"""open_child_window("{_url}","{target}","{win_options}");""",
        # ~ })
        # ~ await websocket.send(msg)


class OrdersPage:

    def __init__(self):

        self.page_limit = 50

    def populate_file_table(self, websocket, filter_text=''):

        name_list_ = []
        for n in os.listdir(SETTINGS.WEBENGINE_DOWNLOAD_PATH):
            if filter_text.lower() in n.lower():
                name_list_.append(n)
            if len(name_list_) >= self.page_limit:
                break

        name_list_.sort(reverse=True)

        html_ = ""
        for i, o in enumerate(name_list_):
            html_ += f"""<tr> 
                <td>{o}</td> 
                <td><div class="edit" id="file_edit_{i}"></div></td> 
                <td><div class="info" id="file_info_{i}"></div></td> 
                <td><div class="remove" id="file_remove_{i}"></div></td> 
            </tr>"""

        msg = json.dumps({
            'type': 'html',
            'target': 'file_tbody',
            'value': html_,
        })
        t = websocket.send(msg)
        asyncio.ensure_future(t)

    async def refresh_page(self, msg_dict, websocket, parent):

        logging.warning(f"self:{self}, msg_dict:{msg_dict}, websocket:{websocket}, parent:{parent}.")

        data = {
            'jar': [22*'a', 22*'b', 22*'c']*6,
            'order': [22*'a', 22*'b', 22*'c']*6,
            'file': [22*'a', 22*'b', 22*'c']*6,
        }

        ctx = {
            'data': data,
        }

        html_ = JINJA_ENVIRONMENT.get_template("orders_page.html").render(**ctx)

        msg = json.dumps({
            'type': 'html',
            'target': 'orders_page',
            'value': html_,
        })
        await websocket.send(msg)

    async def click(self, msg_dict, websocket, parent):

        logging.warning(f"self:{self}, msg_dict:{msg_dict}, websocket:{websocket}, parent:{parent}.")
        open_alert_dialog(f"msg_dict:{msg_dict}", websocket)

    async def keyup(self, msg_dict, websocket, parent):

        logging.warning(f"self:{self}, msg_dict:{msg_dict}, websocket:{websocket}, parent:{parent}.")
        # ~ open_alert_dialog(f"msg_dict:{msg_dict}", websocket)
        filter_text = msg_dict.get('el_value', '')
        self.populate_file_table(websocket, filter_text)

class BrowserPage:

    async def refresh_page(self, msg_dict, websocket, parent):

        logging.warning(f"self:{self}, msg_dict:{msg_dict}, websocket:{websocket}, parent:{parent}.")

        msg = json.dumps({
            'type': 'html',
            'target': 'browser_page',
            'value': "<h2>BROWSER</h2>",
        })
        await websocket.send(msg)

        _url = SETTINGS.WEBENGINE_CUSTOMER_URL
        target = "childBrowserWin"
        win_options = "popup=1,left=0,top=0,height=916,width=1980,status=yes,toolbar=no,menubar=no,location=no"
        open_child_window(websocket, _url, target, win_options)

    async def click(self, msg_dict, websocket, parent):

        logging.warning(f"self:{self}, msg_dict:{msg_dict}, websocket:{websocket}, parent:{parent}.")

class ToolsPage:

    async def refresh_page(self, msg_dict, websocket, parent):

        # ~ open_alert_dialog("refresh_page", websocket)

        ctx = {
            'data': {},
        }

        html_ = JINJA_ENVIRONMENT.get_template("tools_page.html").render(**ctx)

        msg = json.dumps({
            'type': 'html',
            'target': 'tools_page',
            'value': html_,
        })
        await websocket.send(msg)

    def show_msg_on_ui(self, msg, websocket):

        msg_ = json.dumps({
            'type': 'html',
            'target': 'tools_msg_from_server',
            'value': msg + "<br/>",
            'mode': 'append',
        })
        t = websocket.send(msg_)
        asyncio.ensure_future(t)

    async def change(self, msg_dict, websocket, parent):

        logging.warning(f"self:{self}, msg_dict:{msg_dict}, websocket:{websocket}, parent:{parent}.")
        s_ = json.dumps(msg_dict, indent=2)
        self.show_msg_on_ui(f'msg_dict:{s_}', websocket)

    async def click(self, msg_dict, websocket, parent):

        logging.warning(f"self:{self}, msg_dict:{msg_dict}, websocket:{websocket}, parent:{parent}.")
        if msg_dict.get('el_id') == 'tools_close_child_windows':
            close_child_windows(websocket, "alert_win_")
            self.show_msg_on_ui('closed all children', websocket)
        elif msg_dict.get('el_id') == 'tools_open_alert_dialog':
            open_alert_dialog("tools_open_alert_dialog", websocket)
            self.show_msg_on_ui('a dialog has been opened', websocket)
        elif 'openurl' == msg_dict.get('el_id').split('_')[0]:
            _url = msg_dict.get('el_value')
            target = "childBrowserWin"
            win_options = "popup=1,left=0,top=0,height=916,width=1980,status=yes,toolbar=no,menubar=no,location=no"
            open_child_window(websocket, _url, target, win_options)
            self.show_msg_on_ui(f"opened '{_url}' in child window '{target}'", websocket)
        else:
            s_ = json.dumps(msg_dict, indent=2)
            self.show_msg_on_ui(f'msg_dict:{s_}', websocket)

class HelpPage:

    async def refresh_page(self, msg_dict, websocket, parent):

        close_child_windows(websocket)

        logging.warning(f"self:{self}, msg_dict:{msg_dict}, websocket:{websocket}, parent:{parent}.")

        msg = json.dumps({
            'type': 'html',
            'target': 'help_page',
            'value': "<h2>HELP</h2>",
        })
        await websocket.send(msg)

    async def click(self, msg_dict, websocket, parent):

        logging.warning(f"self:{self}, msg_dict:{msg_dict}, websocket:{websocket}, parent:{parent}.")

class RemoteUiMessageHandler: # pylint: disable=too-few-public-methods

    pages = {
        'home_page': HomePage(),
        'orders_page': OrdersPage(),
        'browser_page': BrowserPage(),
        'tools_page': ToolsPage(),
        'help_page': HelpPage(),
    }

    @classmethod
    async def notify_msg(cls, parent, websocket, type_, msg):
        if 'device:machine:status_' in type_:
            head_index = int(type_.split('_')[1])
            await cls.pages['home_page'].refresh_head(parent, websocket, head_index)
        elif 'live_can_list' in type_:
            logging.warning(f"msg:{msg}.")

    @classmethod
    async def handle_msg(cls, msg, websocket, parent):

        # ~ logging.warning(f"websocket:{websocket}, msg:{msg}.")
        try:
            msg_dict = json.loads(msg)
            logging.warning(f"msg_dict:{msg_dict}.")
            event = msg_dict.get('event')
            page_id = msg_dict.get('page_id')
            page = cls.pages.get(page_id)

            if page:
                handler = getattr(page, event)
                if handler:
                    ret = await handler(msg_dict, websocket, parent)
                    logging.warning(f"ret:{ret}.")

        except Exception:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())

class WsMessageHandler: # pylint: disable=too-few-public-methods

    parent = None

    @classmethod
    async def handle_msg(cls, msg, websocket, parent):

        logging.warning(f"websocket:{websocket}, msg:{msg}.")

        try:

            cls.parent = parent

            msg_dict = json.loads(msg)

            if msg_dict.get("command"):

                if hasattr(cls, msg_dict["command"]):
                    _callable = getattr(cls, msg_dict["command"])
                    answer = await _callable(msg_dict, websocket)

                logging.warning(f"answer:{answer}")

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
    async def change_language(cls, msg_dict, websocket): # pylint: disable=unused-argument

        params = msg_dict.get("params", {})
        lang = params.get("lang")
        set_language(lang)

    @classmethod
    async def ask_aliases(cls, msg_dict, websocket): # pylint: disable=unused-argument

        _alias_file = os.path.join(SETTINGS.DATA_PATH, "pigment_alias.json")
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
        S = SETTINGS
        s_ = [f"{i}: {getattr(S, i)}" for i in dir(S) if not i.startswith("_") and not isinstance(getattr(S, i), types.ModuleType)]

        answ_ = html.unescape('<br/>'.join(s_))
        logging.warning(f"answ_:{answ_}.")

        answer = json.dumps({
            'type': 'ask_settings_answer',
            'value': answ_,
        })
        await websocket.send(answer)

    @classmethod
    async def create_order_from_file(cls, msg_dict, websocket):
        params = msg_dict.get("params", {})
        file_name = params.get("file_name")
        logging.warning(f"file_name:{file_name}.")
        try:
            _path = SETTINGS.WEBENGINE_DOWNLOAD_PATH.strip()
            path_to_file = os.path.join(_path, file_name)

            get_application_instance().main_window.order_page.populate_order_table()
            order_list = get_application_instance().create_orders_from_file(path_to_file=path_to_file, n_of_jars=1, silent=True)
            get_application_instance().main_window.order_page.populate_order_table()

            order_nr_ = order_list and order_list[0] and order_list[0].order_nr
            if order_nr_:
                msg_ = tr_("<h4>created order {} from file:{}</h4>").format(order_nr_, file_name)
            else:
                msg_ = tr_("<h4>can't create order from file:{}</h4>").format(file_name)
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

        _path = SETTINGS.WEBENGINE_DOWNLOAD_PATH.strip()
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

        if self.remote_ui_clients:
            for client in self.remote_ui_clients:
                await RemoteUiMessageHandler.notify_msg(self.parent, client, type_, msg)

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
                'value': SETTINGS.LANGUAGE,
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
