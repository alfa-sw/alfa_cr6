# coding: utf-8

""" test DYMO print label file using CUPS driver """

# pylint: disable=too-many-function-args
# pylint: disable=missing-function-docstring

import os
import pathlib
import traceback
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
PATH_TMP_FILE = str(HERE) + os.path.sep + 'tmp_file.jpg'
PATH_COMPLETE_FILE = str(HERE) + os.path.sep + 'label.png'


DEFAULT_TEST_SETTINGS = {'ean13': '201027001001',
                         'label_details': 'LY9C VOLKSWAGEN-AUDI\nA4'}


def create_printable_image():
    """create a printable image .png for DYMO 450 Turbo
            1 step - create barcode img
            2 step - create a new img adding inside of it the one created at step 1
            3 step - add text contents in the img created at step 2"""

    try:
        # STEP 1
        print(PATH_TMP_FILE)
        if not os.path.exists(PATH_TMP_FILE):
            with open(PATH_TMP_FILE, 'w'):
                pass

        with open(PATH_TMP_FILE, 'wb') as file_:
            barcode_img = EAN13(DEFAULT_TEST_SETTINGS.get('ean13'), writer=ImageWriter())
            options = {
                # 'dpi': 200,
                # 'module_height': 5,
                # 'quiet_zone': 0,
                'font_size': 24,
                'text_distance': 0.75,
            }
            barcode_img.write(file_, options)

        # STEP 2
        img = Image.open(PATH_TMP_FILE, 'r')
        img_w, img_h = img.size
        img = img.resize((523, int(img_h * .65)), Image.ANTIALIAS)
        background = Image.new('RGBA', (600, 300), (255, 255, 255, 255))
        bg_w, bg_h = background.size
        offset = ((bg_w - img_w) // 2, ((bg_h - img_h) // 2) + 80)
        background.paste(img, offset)
        background.save(PATH_COMPLETE_FILE)
        if os.path.exists(PATH_TMP_FILE):
            os.remove(PATH_TMP_FILE)

        # STEP 3
        img = Image.open(PATH_COMPLETE_FILE)
        draw = ImageDraw.Draw(img)
        font = ImageFont.truetype(r'/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf', 40)
        # testo = """LY9C VOLKSWAGEN-AUDI\nA4"""
        draw.text((40, 10), DEFAULT_TEST_SETTINGS.get('label_details'), "black", font=font)
        img.save(PATH_COMPLETE_FILE)
    except Exception:   # pylint: disable=broad-except
        print(traceback.format_exc())


def send_cups_print_cmd():
    """ send CUP print cmd
            more info on: https://www.cups.org/doc/options.html
    """

    # TODO: improve with job queue check
    os.system('lp -o media=Custom.20x80mm {}'.format(PATH_COMPLETE_FILE))


def main():
    create_printable_image()
    # send_cups_print_cmd()


if __name__ == "__main__":
    main()

# useful links
#
# https://pypi.org/project/python-barcode/
# https://python-barcode.readthedocs.io/en/stable/writers/index.html
# https://github.com/WhyNotHugo/python-barcode/issues/17
