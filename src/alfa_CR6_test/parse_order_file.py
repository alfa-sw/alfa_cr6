#!/usr/bin/python3

import os
import sys
import logging
import json
import traceback

from alfa_CR6_backend.order_parser import OrderParser


def main():

    try:
        logging.basicConfig(
            stream=sys.stdout, level='WARNING',
            format="[%(asctime)s]%(levelname)s %(funcName)s() %(filename)s:%(lineno)d %(message)s")

        _parser = OrderParser()

        for path_to_file in sys.argv[1:]:

            properties = _parser.parse(path_to_file)

            logging.warning(f"{path_to_file} ingredients:{len(properties.get('ingredients', []))}")

            assert properties.get('ingredients')
            logging.warning(json.dumps(properties, indent=2, ensure_ascii=False))

    except:

        logging.error(traceback.format_exc())
        logging.error(f"input file:{sys.argv[1:]}")


main()

"""
. /opt/alfa_cr6/venv/bin/activate
python ./src/alfa_CR6_test/parse_order_file.py /opt/PROJECTS/alfa_cr6/doc/__hidden__/KCC/kcc_formula_examples/*.json
python ./src/alfa_CR6_test/parse_order_file.py /opt/PROJECTS/alfa_cr6/doc/__hidden__/KCC/kcc_formula_examples/pdf_spectro/*.pdf
python ./src/alfa_CR6_test/parse_order_file.py /opt/PROJECTS/alfa_cr6/doc/Sikkens_AkzoNobel_formulas/*.pdf
python ./src/alfa_CR6_test/parse_order_file.py /opt/PROJECTS/alfa_cr6/doc/SW_formula_examples/*dat*
python ./src/alfa_CR6_test/parse_order_file.py /opt/PROJECTS/alfa_cr6/doc/__hidden__/mutlichem/*.csv
python ./src/alfa_CR6_test/parse_order_file.py /opt/PROJECTS/alfa_cr6/doc/__hidden__/Noroo/*.xml
"""
