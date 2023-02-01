# coding: utf-8

""" dymo printer module """

# pylint: disable=too-many-function-args
# pylint: disable=missing-function-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=logging-fstring-interpolation, consider-using-f-string

import traceback
import logging
import subprocess

from alfa_CR6_backend.globals import (create_printable_image_from_jar,create_printable_image_for_pigment)

def _exec_cmd(command, shell=False):

    command_list = command.split(' ')
    logging.debug('command_list -> {}'.format(command_list))
    os_cmd_reply = subprocess.check_output(command_list, shell=shell, stderr=subprocess.STDOUT).decode()
    reply_cmd = [i.strip() for i in os_cmd_reply.split('\n')]
    return reply_cmd


def _check_dymo_printer_presence():
    lsusb_res = _exec_cmd('lsusb', True)
    return [elem for elem in lsusb_res if 'Dymo-CoStar' in elem]


def _dymo_print_tmp_image(_printable_image_pth, fake=False):

    ret = {}
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

    return ret

def dymo_print_jar(jar):

    logging.debug(f'jar: {jar}')

    ret = {}
    try:
        _printable_image_pth = create_printable_image_from_jar(jar)
        ret = _dymo_print_tmp_image(_printable_image_pth)
    except Exception:   # pylint: disable=broad-except
        logging.error(traceback.format_exc())
        ret = {'result': 'NOK', 'msg': traceback.format_exc()}

    return ret

def dymo_print_pigment_label(barcode_txt, pigment_name, pipe_name):

    ret = {}
    try:
        _printable_image_pth = create_printable_image_for_pigment(barcode_txt, pigment_name, pipe_name)
        ret = _dymo_print_tmp_image(_printable_image_pth)
    except Exception:   # pylint: disable=broad-except
        logging.error(traceback.format_exc())
        ret = {'result': 'NOK', 'msg': traceback.format_exc()}

    return ret
