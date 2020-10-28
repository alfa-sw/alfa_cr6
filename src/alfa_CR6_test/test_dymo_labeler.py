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
from PIL import Image
from PIL import ImageFont
from PIL import ImageDraw
from barcode import EAN13                   # pylint: disable=import-error
from barcode.writer import ImageWriter      # pylint: disable=import-error



#
#	TO RUN THIS TEST IS NECESSARY INSTALL THOSE PIP PKG INTO VENV:
#   pip install python-barcode
#   pip install Pillow
#

HERE = pathlib.Path().absolute()
# PATH_TMP_FILE = os.path.join(str(HERE), os.path.sep, 'tmp_file.jpg')
# PATH_COMPLETE_FILE = os.path.join(str(HERE), os.path.sep, 'label.png')
PATH_TMP_FILE = str(HERE) + os.path.sep + 'tmp_file.png'
PATH_COMPLETE_FILE = str(HERE) + os.path.sep + 'label.png'


DEFAULT_TEST_SETTINGS = {'ean13': '201027001001',
                         'label_details': 'LY9C VOLKSWAGEN-AUDI\nA4',
                         'printer_model': 'Dymo',}


def _create_printable_image():
    """create a printable image .png for DYMO 450 Turbo
            1 step - create barcode img
            2 step - create a new img adding inside of it the one created at step 1
            3 step - add text contents in the img created at step 2"""

    response = {}
    try:
        # STEP 1
        print(PATH_TMP_FILE)
        if not os.path.exists(PATH_TMP_FILE):
            with open(PATH_TMP_FILE, 'w'):
                pass

        with open(PATH_TMP_FILE, 'wb') as file_:
            barcode_img = EAN13(DEFAULT_TEST_SETTINGS.get('ean13'), writer=ImageWriter())
            #options = {
             #    'dpi': 100,
             #   # 'module_height': 5,
             #   # 'quiet_zone': 0,
             #   'font_size': 24,
             #   'text_distance': 0.75,
             #   #'compress':True,
            #}
            options = {
                'dpi': 100,
                # 'module_height': 5,
                # 'quiet_zone': 0,
                'font_size': 6,
                'text_distance': 0.75,
                'compress':True,
                }
            barcode_img.write(file_, options)

        # STEP 2
        img = Image.open(PATH_TMP_FILE, 'r')
        img_w, img_h = img.size
        # img = img.resize((523, int(img_h * .65)), Image.ANTIALIAS)
        img = img.resize((523, int(img_h * .65)))
        background = Image.new('RGBA', (600, 300), (255, 255, 255, 255))
        bg_w, bg_h = background.size
        offset = ((bg_w - img_w) // 2, ((bg_h - img_h) // 2) + 80)
        background.paste(img, offset)
        background.save(PATH_COMPLETE_FILE, optimize=True, quality=20)
        if os.path.exists(PATH_TMP_FILE):
            os.remove(PATH_TMP_FILE)

        # STEP 3
        img = Image.open(PATH_COMPLETE_FILE)
        draw = ImageDraw.Draw(img)
        # TODO: in future get font from folder_font
        font_path = '/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf'
        if not os.path.exists(font_path):
            font_path = '/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf'
        font = ImageFont.truetype(font_path, 40)
        draw.text((40, 10), DEFAULT_TEST_SETTINGS.get('label_details'), "black", font=font)
        img.save(PATH_COMPLETE_FILE, optimize=True, quality=20)
        logging.info('Image created at {}'.format(PATH_COMPLETE_FILE))
        response = {'result': 'OK', 'file': PATH_COMPLETE_FILE}
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
        _res = _format_reply('lp -o media=Custom.20x80mm {}'.format(_path))
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


def parse_options(args=sys.argv[1:]):   # pylint: disable=dangerous-default-value

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


def main():
    fmt_ = '[%(asctime)s]%(levelname)s %(funcName)s() %(filename)s:%(lineno)d %(message)s'
    logging.basicConfig(stream=sys.stdout, level=logging.INFO, format=fmt_)

    options = parse_options()
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


if __name__ == "__main__":
    main()

# useful links
#
# https://pypi.org/project/python-barcode/
# https://python-barcode.readthedocs.io/en/stable/writers/index.html
# https://github.com/WhyNotHugo/python-barcode/issues/17
