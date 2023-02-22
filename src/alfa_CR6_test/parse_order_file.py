#!/usr/bin/python3

import os
import sys
import logging
import json
import traceback

from alfa_CR6_backend.order_parser import OrderParser

LOG_LEVEL = 'ERROR'
# ~ LOG_LEVEL = 'WARNING'
# ~ LOG_LEVEL = 'INFO'

def main():

    try:
        logging.basicConfig(
            stream=sys.stdout, level=LOG_LEVEL,
            format="[%(asctime)s]%(levelname)s %(funcName)s() %(filename)s:%(lineno)d %(message)s")

        _parser = OrderParser()

        for path_to_file in sys.argv[1:]:

            try:
                properties_list = _parser.parse(path_to_file)

                count = 0
                for properties in properties_list:
                    # ~ logging.warning(f"{path_to_file} ingredients:{len(properties.get('ingredients', []))}")

                    # ~ logging.warning(json.dumps(properties, indent=2, ensure_ascii=False))
                    # ~ logging.warning(f"extra_lines_to_print:{properties['extra_lines_to_print']}")
                    with open(path_to_file + f'.{count}.json', 'w') as f:
                        json.dump(properties, f, indent=2, ensure_ascii=False)
                        count += 1

                    logging.error(f"input file:{f}")
                    logging.error(json.dumps(properties['meta']["extra_info"], indent=2))

                    assert properties.get('ingredients')

            except:
                logging.error(traceback.format_exc())

    except:
        logging.error(traceback.format_exc())

    for f in sys.argv[1:]:
        logging.warning(f"input file:{f}")


main()

"""
. /opt/alfa_cr6/venv/bin/activate
python /opt/PROJECTS/alfa_cr6/src/alfa_CR6_test/parse_order_file.py /opt/PROJECTS/alfa_cr6/doc/__hidden__/KCC/kcc_formula_examples/*.json
python /opt/PROJECTS/alfa_cr6/src/alfa_CR6_test/parse_order_file.py /opt/PROJECTS/alfa_cr6/doc/__hidden__/KCC/kcc_formula_examples/pdf_spectro/*.pdf
python /opt/PROJECTS/alfa_cr6/src/alfa_CR6_test/parse_order_file.py /opt/PROJECTS/alfa_cr6/doc/Sikkens_AkzoNobel_formulas/*.pdf
python /opt/PROJECTS/alfa_cr6/src/alfa_CR6_test/parse_order_file.py /opt/PROJECTS/alfa_cr6/doc/SW_formula_examples/*dat*
python /opt/PROJECTS/alfa_cr6/src/alfa_CR6_test/parse_order_file.py /opt/PROJECTS/alfa_cr6/doc/__hidden__/mutlichem/*.csv
python /opt/PROJECTS/alfa_cr6/src/alfa_CR6_test/parse_order_file.py /opt/PROJECTS/alfa_cr6/doc/__hidden__/Noroo/*.xml
"""
