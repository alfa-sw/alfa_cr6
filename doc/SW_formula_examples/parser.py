# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name
# pylint: disable=too-many-lines

import sys
import logging
import traceback
import json
import codecs
import subprocess


def get_encoding(path_to_file, key=None):

    cmd_ = ["file", "-b", "--mime-encoding", path_to_file]
    try:
        p = subprocess.run(cmd_, stdout=subprocess.PIPE)
        mime_encoding = p.stdout.decode().strip()
        logging.warning(f"cmd_:{cmd_}, mime_encoding:{mime_encoding}")
        assert mime_encoding
        return mime_encoding
    except Exception:
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
        except Exception:
            logging.warning(traceback.format_exc())
        else:
            logging.warning(f"path_to_file:{path_to_file}, e:{e}")
            return e

def parse_dat_order_old(path_to_dat_file):

    def __find_items_in_line(items, l):
        return not [i for i in items if i not in l]

    sw_dat_keys = """
    Marca
    Regione
    Codicecolore
    Variante
    Nomecolore
    Secondo-nome
    Anno
    Contrassegno
    Qualità
    Fondo
    Pittogrammi
    Data modifica
    Quantità
    Cumulativo
    """.split('\n')

    sw_dat_start_line_items = [
        "Tinta Base", "Peso", "Prezzo netto di vendita"]
    sw_dat_end_line_items = ["Totale"]

    properties = {
        "meta": {},
        "ingredients": [],
    }
    e = __get_encoding(path_to_dat_file)

    with codecs.open(path_to_dat_file, encoding=e) as fd:
        lines = fd.readlines()

    collecting_ingredients = False
    for l in lines[:]:
        toks = l.split(":")
        if collecting_ingredients:
            if __find_items_in_line(sw_dat_end_line_items, l):
                collecting_ingredients = False
            elif l.strip():
                toks = [t.strip() for t in l.split()]
                # ~ logging.warning(f"toks:{toks}")
                if toks:
                    new_item = {}
                    new_item["pigment_name"] = toks[0]
                    new_item["weight(g)"] = round(float(toks[1].replace(",", ".")), 4)
                    new_item["description"] = toks[2]
                    properties["ingredients"].append(new_item)
            lines.remove(l)
        elif not collecting_ingredients:
            if __find_items_in_line(sw_dat_start_line_items, l):
                collecting_ingredients = True
                lines.remove(l)
            elif len(toks) == 2:
                k = toks[0].strip()
                v = toks[1].strip()
                if k in sw_dat_keys:
                    properties["meta"][k] = v
                    lines.remove(l)

    properties["meta"]["extra_info"] = [
        l.replace('\n', '').replace('\r', '').replace('\t', '').strip() for l in lines if l.strip()]

    return properties




def parse_dat_order(path_to_dat_file):

    def __find_items_in_line(items, l):
        return not [i for i in items if i not in l]

    sw_dat_keys_string = """
    Marca
    Regione
    Codicecolore
    Variante
    Nomecolore
    Secondo-nome
    Anno
    Contrassegno
    Qualità
    Fondo
    Pittogrammi
    Data modifica
    Quantità
    Cumulativo
    """

    sw_dat_keys = [s.strip() for s in sw_dat_keys_string.split('\n')]

    sw_dat_start_line_items = [
        "Tinta Base", "Peso"]
    sw_dat_end_line_items = ["Totale"]

    properties = {
        "meta": {},
        "ingredients": [],
    }
    e = get_encoding(path_to_dat_file)

    with codecs.open(path_to_dat_file, encoding=e) as fd:
        lines = fd.readlines()

    collecting_ingredients = False
    for l in lines[:]:
        toks = l.split(":")
        if collecting_ingredients:
            if __find_items_in_line(sw_dat_end_line_items, l):
                collecting_ingredients = False
            elif l.strip():
                toks = [t.strip() for t in l.split()]
                # ~ logging.warning(f"toks:{toks}")
                if toks:
                    new_item = {}
                    new_item["pigment_name"] = toks[0]
                    new_item["weight(g)"] = round(float(toks[1].replace(",", ".")), 4)
                    new_item["description"] = "" if len(toks) <= 2 else toks[2]
                    properties["ingredients"].append(new_item)
            lines.remove(l)
        elif not collecting_ingredients:
            if __find_items_in_line(sw_dat_start_line_items, l):
                collecting_ingredients = True
                lines.remove(l)
            elif len(toks) == 2:
                k = toks[0].strip()
                v = toks[1].strip()
                if k in sw_dat_keys:
                    properties["meta"][k] = v
                    lines.remove(l)

    properties["meta"]["extra_info"] = [
        l.replace('\n', '').replace('\r', '').replace('\t', '').strip() for l in lines if l.strip()]

    return properties


if __name__ == "__main__":

    for file_name in sys.argv[1:]:
        p = parse_dat_order(file_name)
        print("*********")
        print("file_name:{}.".format(file_name))
        print("ingredients:{}.".format(json.dumps(p["ingredients"], indent=2)))
        print("meta:{}.".format(json.dumps(p["meta"], indent=2)))
        print("meta['Quantità']:{}.".format(p["meta"]['Quantità']))
        print("==========")
