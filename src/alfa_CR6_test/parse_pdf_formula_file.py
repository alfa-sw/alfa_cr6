#!/usr/bin/python3

import os
import sys
import logging
import json
import glob

from alfa_CR6_backend.base_application import parse_pdf_order


def main():

    logging.basicConfig(
        stream=sys.stdout, level='WARNING',
        format="[%(asctime)s]%(levelname)s %(funcName)s() %(filename)s:%(lineno)d %(message)s")

    for f_name in sys.argv[1:]:

        print(f_name)    
        p = parse_pdf_order(f_name, 0)
        logging.warning(json.dumps(p, indent=2))

main()
