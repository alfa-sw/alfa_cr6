# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name
# pylint: disable=too-many-lines
# pylint: disable=broad-except

import sys
import logging
import traceback
import json
import codecs
import subprocess


def get_encoding(path_to_file, key=None):

    cmd_ = ["file", "-b", "--mime-encoding", path_to_file]
    try:
        proc = subprocess.run(cmd_, stdout=subprocess.PIPE, check=False)
        mime_encoding = proc.stdout.decode().strip()
        logging.warning(f"cmd_:{cmd_}, mime_encoding:{mime_encoding}")
        assert mime_encoding
        return mime_encoding
    except Exception:                      # pylint: disable=broad-except
        logging.warning(traceback.format_exc())

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
        except Exception:                 # pylint: disable=broad-except
            logging.warning(traceback.format_exc())
        else:
            logging.warning(f"path_to_file:{path_to_file}, e:{e}")
            return e


def parse_kcc_pdf_order(path_to_pdf_file):   # pylint: disable=too-many-locals
    
    header_id = "KCC Color Navi Formulation"

    path_to_txt_file = "{0}.txt".format(path_to_pdf_file)

    cmd_ = ["pdftotext", path_to_pdf_file, path_to_txt_file]
    subprocess.run(cmd_, check=False)
    e = get_encoding(path_to_txt_file)

    section_separator = "__________________________"

    with codecs.open(path_to_txt_file, encoding=e) as fd:
        lines = [l.strip() for l in fd.readlines()]

    assert header_id in lines[0], Exception("missing header:'{}'".format(header_id))

    section = 0
    section_cntr = 0
    meta = {}
    ingredients = []
    extra_info = []
    for i, l in enumerate(lines):
        if not l:
            continue
        try:
            if section_separator in l:
                section += 1
                section_cntr = 0
            else:
                if section == 0:
                    toks = [t_ for t_ in [t.strip() for t in l.split(":")] if t_]
                    if len(toks) == 2:
                        meta[toks[0]] = toks[1]
                elif section == 1:
                    if section_cntr % 2 == 0:
                        toks = [t_ for t_ in [t.strip() for t in l.split(":")] if t_]
                        description = toks[0]
                        name = toks[1]
                    else:
                        value = round(float(l.split('(G)')[0]), 4)
                        new_item = {}
                        new_item["pigment_name"] = name
                        new_item["weight(g)"] = value
                        new_item["description"] = description
                        ingredients.append(new_item)
                elif section == 2:
                    extra_info.append(l)
                section_cntr += 1
        except Exception:              # pylint: disable=broad-except
            logging.error(f"fmt error in file:{path_to_txt_file} : line:{i}")
            logging.error(traceback.format_exc())

    meta["extra_info"] = "\n".join(extra_info)
    properties = {
        "meta": meta,
        "ingredients": ingredients,
    }

    return properties


if __name__ == "__main__":

    for file_name in sys.argv[1:]:
        p = parse_kcc_pdf_order(file_name)
        print("*********")
        print("file_name:{}.".format(file_name))
        print("ingredients:{}.".format(json.dumps(p["ingredients"], indent=2)))
        print("meta:{}.".format(json.dumps(p["meta"], indent=2)))
        print("==========")
