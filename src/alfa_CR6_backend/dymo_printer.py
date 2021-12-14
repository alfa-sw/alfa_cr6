# coding: utf-8

""" dymo printer module """

# pylint: disable=too-many-function-args
# pylint: disable=missing-function-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long

import os
import traceback
import logging
import subprocess
from barcode import EAN13                   # pylint: disable=import-error
from barcode.writer import ImageWriter      # pylint: disable=import-error

from alfa_CR6_backend.globals import import_settings


def _create_printable_image(recipe_barcode, line_1, line_2, line_3):
    """ create a printable image .png for DYMO 450 """

    settings = import_settings()

    tmp_barcode_image = f"/opt/alfa_cr6/tmp/tmp_file.png"

    response = {}
    try:

        if not os.path.exists(tmp_barcode_image):
            with open(tmp_barcode_image, 'w'):
                pass
            logging.warning(f'empty file created at:{tmp_barcode_image}')

        with open(tmp_barcode_image, 'wb') as file_:
            recipe_barcode_text = f'{recipe_barcode}'
            barcode_img = EAN13(recipe_barcode_text, writer=ImageWriter())

            options = {
                'dpi': 250,
                'module_height': 7,
                'font_size': 15,
                'text_distance': 0.75,
                'compress': False,
            }

            if hasattr(settings, 'PRINT_LABEL_FONT_PATH') and settings.PRINT_LABEL_FONT_PATH:
                options.update({'font_path': settings.PRINT_LABEL_FONT_PATH})

            line_1 = _line_lenght_checker(line_1)
            line_2 = _line_lenght_checker(line_2)
            line_3 = _line_lenght_checker(line_3)

            printable_info_list = []
            printable_info_list.append(recipe_barcode)
            printable_info_list.append(line_1)
            printable_info_list.append(line_2)
            printable_info_list.append(line_3)

            printable_text = '\n'.join(printable_info_list)

            logging.debug(f'printable_text: {printable_text}')

            barcode_img.write(file_, options, printable_text)

        logging.debug(f'Barcode {recipe_barcode} label created at {tmp_barcode_image}')
        response = {'result': 'OK', 'file': tmp_barcode_image}
    except Exception:   # pylint: disable=broad-except
        logging.error(traceback.format_exc())
        response = {'result': 'KO', 'error': traceback.format_exc()}

    logging.warning('response: {}'.format(response))
    return response


def _line_lenght_checker(line, line_lenght=17):
    logging.debug(f'len: {len(line)} | line_lenght: {line_lenght}')
    if len(line) > line_lenght:
        line = line[:line_lenght]
    logging.debug(f'line: {line}')
    return line


def _format_reply(command, shell=False, loggable=False):
    try:
        command_list = command.split(' ')
        logging.debug('')
        logging.debug('command_list -> {}'.format(command_list))
        os_cmd_reply = subprocess.check_output(command_list, shell=shell, stderr=subprocess.STDOUT).decode()
        reply_cmd = [i.strip() for i in os_cmd_reply.split('\n')]
        if loggable:
            logging.debug('reply_cmd({}): {}'.format(type(reply_cmd), reply_cmd))
        reply = {'result': 'OK', 'data': reply_cmd}
    except subprocess.CalledProcessError as exc:
        err_code = exc.returncode
        err_output = exc.output.decode().rstrip()
        logging.error(f'command "{command}" FAILED ({err_code}) | reason: {err_output}')
        reply = {'result': 'KO', 'error': err_output}

    return reply


def _check_dymo_printer_presence():

    _res_ = _format_reply('lsusb', True, True)
    _res = _res_.get('data')

    if [elem for elem in _res if 'Dymo-CoStar' in elem]:
        response = {'result': 'OK', 'msg': 'Dymo plugged'}
    else:
        response = {'result': 'KO', 'error': 'Dymo not plugged'}

    return response


def _print_label(barcode, line_1, line_2, line_3, fake):
    res_printable_barcode = _create_printable_image(barcode, line_1, line_2, line_3)

    if res_printable_barcode.get('result') == 'OK':
        _path = res_printable_barcode.get('file')
        print_cups_cmd = f'lp -o fit-to-page {_path}'
        logging.debug(f'print_cups_cmd: {print_cups_cmd}')

        if not fake:
            #_res = _format_reply(print_cups_cmd)
            # response.update({'result': 'OK', 'data': _res[0]})
            # res_print = _res[0]
            res_print = _format_reply(print_cups_cmd)
        else:
            res_print = {'result': 'OK', 'message': 'Printing label ..'}
    else:
        logging.error('IMPOSSIBILE TO CREATE THE LABEL')
        res_print = res_printable_barcode.get('error')

    return res_print


def dymo_print(barcode=201027001001, line_1='', line_2='', line_3='', fake=False):
    logging.debug(f'barcode: {barcode}, {[line_1, line_2, line_3]} | fake: {fake}')

    if not fake:
        res_dymo_presence = _check_dymo_printer_presence()
    else:
        res_dymo_presence = {'result': 'OK', 'msg': 'Dymo plugged'}

    logging.warning(f'res_dymo_presence: {res_dymo_presence}')

    if res_dymo_presence.get('result') == 'OK':
        result = _print_label(barcode, line_1, line_2, line_3, fake)
    else:
        result = res_dymo_presence.get('error')

    return result
