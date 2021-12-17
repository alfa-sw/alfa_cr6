# coding: utf-8

import os
import sys
import pathlib
import traceback
import logging

from alfa_CR6_backend.dymo_printer import _create_printable_image

from alfa_CR6_backend.globals import import_settings


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
line_1 = "12345678901234567890"
line_2 = "BBB" "---" "CCC" "+++" "DDD"
line_3 = "현대자동차통근버스"

_create_printable_image(recipe_barcode, line_1, line_2, line_3)

