# coding: utf-8

import os
import sys
import pathlib
import traceback
import time
import logging


"""
gestione etichetta con formati:

25.4x54.02mm (precedente) portrait
lpoptions -d DYMO_LabelWriter_450 -o media=custom_25.4x54.02mm_25.4x54.02mm
lpoptions -d DYMO_LabelWriter_450 -o DymoPrintQuality=Graphics
lpoptions -d DYMO_LabelWriter_450 -o Resolution=300x600dpi

54.02x70.0mm (nuovo)      landscape
lpoptions -d DYMO_LabelWriter_450 -o media=custom_54.02x70.0mm_54.02x70.0mm
lpoptions -d DYMO_LabelWriter_450 -o DymoPrintQuality=Graphics
lpoptions -d DYMO_LabelWriter_450 -o Resolution=300x600dpi


lp -o fit-to-page /home/admin/tmp_file.png 
"""


from alfa_CR6_backend.dymo_printer import (_create_printable_image, dymo_print)

from alfa_CR6_backend.globals import import_settings

# ~ lpoptions -d DYMO_LabelWriter_450 -o media=custom_25.4x54.02mm_25.4x54.02mm
# ~ lpoptions -d DYMO_LabelWriter_450 -o media=custom_25.4x54.02mm
# ~ lpoptions -d DYMO_LabelWriter_450 -o media=custom_54.02x70.0mm_54.02x70.0mm

settings = import_settings()

# ~ settings.PRINT_LABEL_OPTONS = {'font_path': '/usr/share/fonts/truetype/unfonts-extra/UnJamoBatang.ttf'}
# ~ settings.PRINT_LABEL_OPTONS = {'font_path': '/usr/share/fonts/truetype/unfonts-extra/UnJamoDotum.ttf'}
# ~ settings.PRINT_LABEL_OPTONS = {'font_path': '/usr/share/fonts/truetype/unfonts-extra/UnJamoNovel.ttf'}
# ~ settings.PRINT_LABEL_OPTONS = {'font_path': '/usr/share/fonts/truetype/unfonts-extra/UnJamoSora.ttf'}
# ~ settings.PRINT_LABEL_OPTONS = {'font_path': '/usr/share/fonts/truetype/unfonts-extra/UnPenheulim.ttf'}
# ~ settings.PRINT_LABEL_OPTONS = {'font_path': '/usr/share/fonts/truetype/unfonts-extra/UnPen.ttf'}
# ~ settings.PRINT_LABEL_OPTONS = {'font_path': '/usr/share/fonts/truetype/unfonts-extra/UnPilgia.ttf'}
# ~ settings.PRINT_LABEL_OPTONS = {'font_path': '/usr/share/fonts/truetype/unfonts-extra/UnShinmun.ttf'}
# ~ settings.PRINT_LABEL_OPTONS = {'font_path': '/usr/share/fonts/truetype/unfonts-extra/UnTaza.ttf'}
# ~ settings.PRINT_LABEL_OPTONS = {'font_path': '/usr/share/fonts/truetype/unfonts-extra/UnVada.ttf'}
# ~ settings.PRINT_LABEL_OPTONS = {'font_path': '/usr/share/fonts/truetype/unfonts-extra/UnYetgul.ttf'}
# ~ settings.PRINT_LABEL_OPTONS = {'font_path': '/usr/share/fonts/truetype/unfonts-core/UnDotum.ttf'}
settings.PRINT_LABEL_OPTONS = {'font_path': '/usr/share/fonts/truetype/unfonts-core/UnDotumBold.ttf'}
# ~ settings.PRINT_LABEL_OPTONS = {'font_path': '/usr/share/fonts/truetype/unfonts-core/UnGungseo.ttf'}
# ~ settings.PRINT_LABEL_OPTONS = {'font_path': '/usr/share/fonts/truetype/unfonts-core/UnBatang.ttf'}
# ~ settings.PRINT_LABEL_OPTONS = {'font_path': '/usr/share/fonts/truetype/unfonts-extra/UnTaza.ttf'}
# ~ settings.PRINT_LABEL_OPTONS = {'font_path': '/usr/share/fonts/truetype/unfonts-extra/UnVada.ttf'}

recipe_barcode = '201027001001'

settings.PRINT_LABEL_OPTONS['dpi'] = 240
settings.PRINT_LABEL_OPTONS['module_height'] = 10
settings.PRINT_LABEL_OPTONS['module_width'] = .5
settings.PRINT_LABEL_OPTONS['line_lenght'] = 100
settings.PRINT_LABEL_OPTONS['font_size'] = 22
settings.PRINT_LABEL_OPTONS['rotate'] = 270

a = "\n".join([f"{k}: {v}" for k, v in settings.PRINT_LABEL_OPTONS.items()][1:])
b = "12345678901234567890\n*****\n*****\n*****"
c = str(time.asctime())

dymo_print(barcode=201027001001, line_1=a, line_2=b, line_3=c)

logging.warning(time.asctime())

