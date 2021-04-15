#!/usr/bin/python3

import os
import sys
import logging
import json
import glob

from alfa_CR6_backend.base_application import parse_sikkens_pdf_order


def main():

    logging.basicConfig(
        stream=sys.stdout, level='WARNING',
        format="[%(asctime)s]%(levelname)s %(funcName)s() %(filename)s:%(lineno)d %(message)s")

    LIMIT = int(sys.argv[1])

    for i, f_name in list(enumerate(glob.glob('./*.pdf')))[:LIMIT]:

        print(f_name)    
        for fp in sys.argv[2:]:
            p = parse_sikkens_pdf_order(f_name, fp)
            if p:
                logging.warning(json.dumps(p, indent=2))

main()
