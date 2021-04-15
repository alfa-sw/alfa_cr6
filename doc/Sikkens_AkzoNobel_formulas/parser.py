#!/usr/bin/python3

import os
import sys
import time
import logging
import traceback
import asyncio
import json
import codecs
import subprocess
import glob


def get_encoding(path_to_file, key=None):

    cmd_ = ["file", "-b", "--mime-encoding", path_to_file]
    try:
        p = subprocess.run(cmd_, stdout=subprocess.PIPE)
        mime_encoding = p.stdout.decode().strip()
        # ~ logging.warning(f"cmd_:{cmd_}, mime_encoding:{mime_encoding}")
        assert mime_encoding
        return mime_encoding
    except Exception:
        logging.warning(traceback.format_exc())
        return -1

    encodings = [
        'ascii',
        'utf_32',
        'utf_32_be',
        'utf_32_le',
        'utf_16',
        'utf_16_be',
        'utf_16_le',
        'utf_7',
        'utf_8',
        'utf_8_sig']

    for e in encodings:
        try:
            codecs.lookup(e)
            fd = codecs.open(path_to_file, 'br', encoding=e)
            fd.readlines()
            assert key is None or key in fd.read()
            fd.seek(0)
        except (UnicodeDecodeError, UnicodeError):
            logging.info(f"skip e:{e}")
        except Exception:
            logging.warning(traceback.format_exc())
        else:
            logging.warning(f"path_to_file:{path_to_file}, e:{e}")
            return e


def parse(path_to_pdf_file, fixed_pitch=5):

    path_to_txt_file = "{0}.txt".format(path_to_pdf_file)

    cmd_ = " ".join(["pdftotext", "-fixed", f"{fixed_pitch}", path_to_pdf_file, path_to_txt_file]).split(' ')

    subprocess.run(cmd_, check=False)
    e = get_encoding(path_to_txt_file)

    properties = {}

    try:

        with codecs.open(path_to_txt_file, encoding=e) as fd:
            lines = [l.strip() for l in fd.readlines()]
        
        section = 0
        offset_value = 0
        section_cntr = 0
        meta = {}
        ingredients = []
        extra_info = []
        formula_type = None
        for i, l in enumerate(lines):
            if not l:
                continue
            try:
                l = l.strip()
                if section == 0:
                    section_cntr += 1
                    if "Formula Colore" in l:
                        toks = l.split(":")
                        if toks[1:]:
                            formula_type = toks[1].strip()
                        section = 1
                        section_cntr = 0
                    else:
                        if section_cntr > 3:
                            meta[section_cntr - 3] = [t.strip() for t in l.split("   ") if t]
                        else:
                            extra_info.append(l)

                elif section == 1:
                    section_cntr += 1
                    if "Messaggi" in l:
                        section = 2
                        section_cntr = 0
                        extra_info.append(l)

                    elif formula_type:
                        toks = [t.strip() for t in l.split(" ")]
                        if toks[2:]:
                            value_ = toks[-1]
                            if 'cumulativa' in formula_type.lower():
                                 value = float(value_) - offset_value
                                 offset_value += value
                            else:
                                 value = float(value_)
                            new_item = {}
                            new_item["pigment_name"] = toks[0]
                            new_item["weight(g)"] = round(value, 4)
                            new_item["description"] = " ".join([t for t in toks[1:-1] if t])
                            ingredients.append(new_item)
                elif section == 2:
                    section_cntr += 1
                    extra_info.append(l)

            except Exception:              # pylint: disable=broad-except
                logging.error(f"fmt error in file:{path_to_txt_file} : line:{i}")
                logging.error(traceback.format_exc())

        meta["file name"] = os.path.split(path_to_pdf_file)[1]
        meta["extra_info"] = [ "\t".join([t.strip() for t in l.split("   ") if t]) for l in extra_info]
        properties = {
            "meta": meta,
            "ingredients": ingredients,
        }

        total_lt = float(properties['meta'][1][1].split(' ')[0])
        total_gr = sum( [i["weight(g)"] for i in properties['ingredients']] )
        logging.warning(f"total_lt:{total_lt}, total_gr:{total_gr}")

    finally:
        cmd_ = ["rm", "-f", path_to_txt_file]
        subprocess.run(cmd_, check=False)

    return properties


def main():

    logging.basicConfig(
        stream=sys.stdout, level='WARNING',
        format="[%(asctime)s]%(levelname)s %(funcName)s() %(filename)s:%(lineno)d %(message)s")

    LIMIT = int(sys.argv[1])

    for i, f_name in list(enumerate(glob.glob('./*.pdf')))[:LIMIT]:

        print(f_name)    
        for fp in sys.argv[2:]:
            p = parse(f_name, fp)
            if p:
                logging.warning(json.dumps(p, indent=2))

main()
