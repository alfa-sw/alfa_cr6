# coding: utf-8

""" test DYMO print label file using CUPS driver """

# pylint: disable=too-many-function-args
# pylint: disable=missing-function-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long

import os
import sys
import pathlib
import traceback
import logging
import subprocess
import argparse
from barcode import EAN13                   # pylint: disable=import-error
from barcode.writer import ImageWriter      # pylint: disable=import-error


HERE = os.path.dirname(os.path.abspath(__file__))
PATH_TMP_FILE = HERE + os.path.sep + 'tmp_file.png'
DEFAULT_TEST_SETTINGS = {'recipe_barcode': '201027001001',
                         'printer_model': 'Dymo',
                         'recipe_color_code': 'LY9C',
                         'recipe_manufacturer': 'VOLKSWAGEN-AUDI',
                         'recipe_car_model': 'A4',
                         'recipe_qty': '1 L'}


def _create_printable_image():
    """ create a printable image .png for DYMO 450 Turbo """

    response = {}
    try:

        if not os.path.exists(PATH_TMP_FILE):
            with open(PATH_TMP_FILE, 'w'):
                pass

        with open(PATH_TMP_FILE, 'wb') as file_:
            barcode_img = EAN13(DEFAULT_TEST_SETTINGS.get('recipe_barcode'), writer=ImageWriter())

            options = {
                'dpi': 250,
                'module_height': 7,
                # 'quiet_zone': 0,
                'font_size': 15,
                'text_distance': 0.75,
                'compress':False,
                }

            logging.debug('barcode_img({}) -> {}'.format(type(barcode_img), barcode_img))

            custom_text = '{}\n{} {}\n{}\n{}'.format(DEFAULT_TEST_SETTINGS.get('recipe_barcode'),
                                                     DEFAULT_TEST_SETTINGS.get('recipe_color_code'),
                                                     DEFAULT_TEST_SETTINGS.get('recipe_manufacturer'),
                                                     DEFAULT_TEST_SETTINGS.get('recipe_car_model'),
                                                     DEFAULT_TEST_SETTINGS.get('recipe_qty'),)
            barcode_img.write(file_, options, custom_text)

        logging.info('Image created at {}'.format(PATH_TMP_FILE))
        response = {'result': 'OK', 'file': PATH_TMP_FILE}
    except Exception:   # pylint: disable=broad-except
        logging.error(traceback.format_exc())
        response = {'result': 'KO', 'error': traceback.format_exc()}

    logging.debug('response: {}'.format(response))
    return response


def send_cups_cmd(action, params):
    """ send CUP commands
        more info on: https://www.cups.org/doc/options.html
    """

    response = {}

    def _format_reply(command, shell=False, loggable=False):
        command_list = command.split(' ')
        logging.info('')
        logging.info('command_list -> {}'.format(command_list))
        os_cmd_reply = subprocess.check_output(command_list, shell=shell).decode()
        reply = [i.strip() for i in os_cmd_reply.split('\n')]
        if loggable:
            logging.info('reply({}): {}'.format(type(reply), reply))
        return reply

    if action == 'cups_print_label':
        _path = params.get('file')
        _res = _format_reply('lp -o fit-to-page {}'.format(_path))
        response.update({'result': 'OK', 'data': _res[0]})
    elif action == 'cups_check_printer_presence':
        # really really slow :-/
        model = DEFAULT_TEST_SETTINGS.get('printer_model').upper()
        _res = _format_reply('lpinfo -v')
        dymo_printer = [elem for elem in _res if model in elem]
        if dymo_printer:
            response.update({'result': 'OK', 'msg': 'Dymo plugged'})
        else:
            response.update({'result': 'KO', 'error': 'Dymo not plugged'})
    elif action == 'os_check_printer_presence':
        # faster way
        model = DEFAULT_TEST_SETTINGS.get('printer_model')
        _res = _format_reply('lsusb', True)
        label_writer = '-'.join([model, 'CoStar'])
        dymo_printer = [elem for elem in _res if label_writer in elem]
        if dymo_printer:
            response.update({'result': 'OK', 'msg': 'Dymo plugged'})
        else:
            response.update({'result': 'KO', 'error': 'Dymo not plugged'})


    logging.info('response: {}'.format(response))

    return response


def print_label():
    resp = _create_printable_image()

    if resp.get('result') == 'OK':
        send_cups_cmd('cups_print_label', resp)
    else:
        logging.critical('IMPOSSIBILE TO CREATE THE LABEL')


def parse_options(args):   # pylint: disable=dangerous-default-value

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument(
        '-t', '--test',
        help='''\
        test different modes:
        check: check DYMO labeler presence
        print: create label image and print it via CUPS drivers
        all: test both

        e.g python test_dymo_labeler.py -t check''',)

    return parser.parse_args(args)


def test_all(args=["-t", "check"]):

    fmt_ = '[%(asctime)s]%(levelname)s %(funcName)s() %(filename)s:%(lineno)d %(message)s'
    logging.basicConfig(stream=sys.stdout, level=logging.INFO, format=fmt_)

    options = parse_options(args)
    logging.debug("options:{}".format(options))

    if options.test == 'check':
        send_cups_cmd('os_check_printer_presence', {})
    elif options.test == 'print':
        print_label()
    elif options.test == 'all':
        res_ = send_cups_cmd('os_check_printer_presence', {})
        if res_.get('result') == 'OK':
            print_label()
    else:
        logging.warning('Script endend without being used!')
        os.system('python test_dymo_labeler.py -h')


def test_dymo_print()
    dymo_print_res = dymo_print(
        barcode='201027001005',
        line_1='12345678901234567890',
        line_2='acab',
        line_3='0,55 Litro',
        fake=True)
    logging.warning(f'\t res: {dymo_print_res}')


if __name__ == "__main__":
    test_all(sys.argv[1:])

# useful links
#
# https://pypi.org/project/python-barcode/
# https://python-barcode.readthedocs.io/en/stable/writers/index.html
# https://github.com/WhyNotHugo/python-barcode/issues/17
