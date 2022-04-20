# coding: utf-8

""" dymo printer module """

# pylint: disable=too-many-function-args
# pylint: disable=missing-function-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=logging-fstring-interpolation, consider-using-f-string

import os
import traceback
import logging
import subprocess
from barcode import EAN13                   # pylint: disable=import-error
from barcode.writer import ImageWriter      # pylint: disable=import-error

from alfa_CR6_backend.globals import import_settings


def _create_printable_image(recipe_barcode, line_1, line_2, line_3):
    """ create a printable image .png for DYMO 450 """

    recipe_barcode = str(recipe_barcode)

    settings = import_settings()

    tmp_barcode_image = "/opt/alfa_cr6/tmp/tmp_file.png"

    response = None

    if not os.path.exists(tmp_barcode_image):
        with open(tmp_barcode_image, 'w', encoding='UTF-8'):
            pass
        logging.warning(f'empty file created at:{tmp_barcode_image}')

    options = {
        'dpi': 250,
        'module_height': 7,
        'font_size': 15,
        'text_distance': 0.75,
        'compress': False,
        'line_lenght': 24,
        'rotate': 0,
    }

    if hasattr(settings, 'PRINT_LABEL_OPTONS') and settings.PRINT_LABEL_OPTONS:
        options.update(settings.PRINT_LABEL_OPTONS)

    logging.warning(f'options:{options}')

    with open(tmp_barcode_image, 'wb') as file_:
        recipe_barcode_text = f'{recipe_barcode}'

        l_lenght = options.pop('line_lenght')

        line_1 = _line_lenght_checker(line_1, line_lenght=l_lenght)
        line_2 = _line_lenght_checker(line_2, line_lenght=l_lenght)
        line_3 = _line_lenght_checker(line_3, line_lenght=l_lenght)

        printable_info_list = []
        printable_info_list.append(recipe_barcode)
        printable_info_list.append(line_1)
        printable_info_list.append(line_2)
        printable_info_list.append(line_3)

        printable_text = '\n'.join(printable_info_list)

        EAN13(recipe_barcode_text, writer=ImageWriter()).write(file_, options, printable_text)

        response = tmp_barcode_image

    rotate = options.pop('rotate')
    if response and rotate:
        from PIL import Image   # pylint: disable=import-outside-toplevel
        Image.open(tmp_barcode_image).rotate(rotate, expand=1).save(tmp_barcode_image)

    logging.warning('response: {}'.format(response))

    return response


def _line_lenght_checker(line, line_lenght=17):
    logging.debug(f'len: {len(line)} | line_lenght: {line_lenght}')
    if len(line) > line_lenght:
        line = line[:line_lenght]
    logging.debug(f'line: {line}')
    return line

def _exec_cmd(command, shell=False):

    command_list = command.split(' ')
    logging.debug('command_list -> {}'.format(command_list))
    os_cmd_reply = subprocess.check_output(command_list, shell=shell, stderr=subprocess.STDOUT).decode()
    reply_cmd = [i.strip() for i in os_cmd_reply.split('\n')]
    return reply_cmd

def _check_dymo_printer_presence():
    lsusb_res = _exec_cmd('lsusb', True)
    return [elem for elem in lsusb_res if 'Dymo-CoStar' in elem]


def dymo_print(barcode=201027001001, line_1='', line_2='', line_3='', fake=False):

    logging.debug(f'barcode: {barcode}, {[line_1, line_2, line_3]} | fake: {fake}')

    ret = {}
    try:
        _printable_image_pth = _create_printable_image(barcode, line_1, line_2, line_3)
        _dymo_printer_presence = _check_dymo_printer_presence()
        logging.warning(f'_printable_image_pth:{_printable_image_pth}, _dymo_printer_presence:{_dymo_printer_presence}')
        if _printable_image_pth:
            if _dymo_printer_presence:
                _print_cups_cmd = f'lp -o fit-to-page {_printable_image_pth}'
                logging.debug(f'_print_cups_cmd: {_print_cups_cmd}')

                if not fake:
                    res_print = _exec_cmd(_print_cups_cmd)
                    ret = {'result': 'OK', 'msg': res_print}
                else:
                    ret = {'result': 'OK', 'msg': 'Dry run, not printed'}
            else:
                ret = {'result': 'NOK', 'msg': 'Dymo not plugged'}
        else:
            ret = {'result': 'NOK', 'msg': 'Cannot create printable image'}
    except Exception:   # pylint: disable=broad-except
        logging.error(traceback.format_exc())
        ret = {'result': 'NOK', 'msg': traceback.format_exc()}

    return ret
