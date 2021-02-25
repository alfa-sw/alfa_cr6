# coding: utf-8

""" dymo printer module """

# pylint: disable=too-many-function-args
# pylint: disable=missing-function-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=logging-fstring-interpolation
# pylint: disable=line-too-long

import os
import traceback
import logging
import subprocess
from barcode import EAN13                   # pylint: disable=import-error
from barcode.writer import ImageWriter      # pylint: disable=import-error

DEPLOY_PATH = "/opt/alfa_cr6"
TMP_PATH = f"{DEPLOY_PATH}/tmp"
TMP_BARCODE_IMAGE = f"{TMP_PATH}/tmp_file.png"
PRINTER_MODEL = 'Dymo'

def _create_printable_image(recipe_barcode, info_list):
    """ create a printable image .png for DYMO 450 """

    response = {}
    try:

        if not os.path.exists(TMP_BARCODE_IMAGE):
            with open(TMP_BARCODE_IMAGE, 'w'):
                pass
            logging.warning('empty TMP_BARCODE_IMAGE created')

        with open(TMP_BARCODE_IMAGE, 'wb') as file_:
            recipe_barcode_text = f'{recipe_barcode}'
            barcode_img = EAN13(recipe_barcode_text, writer=ImageWriter())

            options = {
                'dpi': 250,
                'module_height': 7,
                'font_size': 15,
                'text_distance': 0.75,
                'compress':False,
                }

            if info_list:
                marca = info_list[0]
                codicecolore = info_list[1]
                secondonome = info_list[2]
                quantità = info_list[3]

                printable_info_list = []
                printable_info_list.append(recipe_barcode)
                if marca:
                    printable_info_list.append(marca)
                if secondonome:
                    printable_info_list.append(secondonome)
                if codicecolore and quantità:
                    printable_info_list.append(f'{codicecolore}    {quantità}')

                printable_text = '\n'.join(printable_info_list)

                logging.warning(f'printable_text: {printable_text}')

            barcode_img.write(file_, options, printable_text)

        logging.warning(f'Barcode {recipe_barcode} label created at {TMP_BARCODE_IMAGE}')
        response = {'result': 'OK', 'file': TMP_BARCODE_IMAGE}
    except Exception:   # pylint: disable=broad-except
        logging.error(traceback.format_exc())
        response = {'result': 'KO', 'error': traceback.format_exc()}

    logging.warning('response: {}'.format(response))
    return response


def _format_reply(command, shell=False, loggable=False):
    try:
        command_list = command.split(' ')
        logging.warning('')
        logging.warning('command_list -> {}'.format(command_list))
        os_cmd_reply = subprocess.check_output(command_list, shell=shell, stderr=subprocess.STDOUT).decode()
        reply_cmd = [i.strip() for i in os_cmd_reply.split('\n')]
        if loggable:
            logging.warning('reply_cmd({}): {}'.format(type(reply_cmd), reply_cmd))
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
    label_writer = '-'.join([PRINTER_MODEL, 'CoStar'])
    dymo_printer = [elem for elem in _res if label_writer in elem]
    if dymo_printer:
        response = {'result': 'OK', 'msg': 'Dymo plugged'}
    else:
        response = {'result': 'KO', 'error': 'Dymo not plugged'}

    return response


def _print_label(barcode, info_list, fake):
    res_printable_barcode = _create_printable_image(barcode, info_list)

    if res_printable_barcode.get('result') == 'OK':
        _path = res_printable_barcode.get('file')
        print_cups_cmd = f'lp -o fit-to-page {_path}'
        logging.warning(f'print_cups_cmd: {print_cups_cmd}')

        if not fake:
            #_res = _format_reply(print_cups_cmd)
            # response.update({'result': 'OK', 'data': _res[0]})
            # res_print = _res[0]
            res_print = _format_reply(print_cups_cmd)
        else:
            res_print = {'result': 'OK', 'message': 'Printing label ..'}
    else:
        logging.critical('IMPOSSIBILE TO CREATE THE LABEL')
        res_print = res_printable_barcode.get('error')

    return res_print


def dymo_print(barcode=201027001001, info_list=[], fake=False):
    logging.warning(f'barcode: {barcode} | fake: {fake}')

    if not fake:
        res_dymo_presence = _check_dymo_printer_presence()
    else:
        res_dymo_presence = {'result': 'OK', 'msg': 'Dymo plugged'}

    logging.warning(f'res_dymo_presence: {res_dymo_presence}')

    if res_dymo_presence.get('result') == 'OK':
        result = _print_label(barcode, info_list, fake)
    else:
        result = res_dymo_presence.get('error')

    return result

if __name__ == "__main__":

    sherwin_hyundai_info = ['HYU    HYUNDAI',   # Marca
                           'U6G',               # Codicecolore
                           'URBAN GREY MET.',   # Secondo-nome
                           '0,55 Litro'         # Quantità
                           ]
    res = dymo_print(barcode='201027001005',
                     info_list =sherwin_hyundai_info,
                     fake=True)
    logging.warning(f'\t res: {res}')

# NOTE
# (venv) galasso@galassoVB:/opt/PROJECTS/alfa_cr6$ python src/alfa_CR6_backend/dymo_printer.py 
# WARNING:root:barcode: 201027001005 | fake: True
# WARNING:root:res_dymo_presence: {'result': 'OK', 'msg': 'Dymo plugged'}
# WARNING:root:printable_text: 201027001005
# HYU    HYUNDAI
# URBAN GREY MET.
# U6G   0,55 Litro
# WARNING:root:Barcode 201027001005 label created at /opt/alfa_cr6/tmp/tmp_file.png
# WARNING:root:response: {'result': 'OK', 'file': '/opt/alfa_cr6/tmp/tmp_file.png'}
# WARNING:root:print_cups_cmd: lp -o fit-to-page /opt/alfa_cr6/tmp/tmp_file.png
# WARNING:root:    res: {'result': 'OK', 'message': 'Printing label ..'}
