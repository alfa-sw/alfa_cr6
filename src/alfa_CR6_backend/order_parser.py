# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name
# pylint: disable=logging-fstring-interpolation, consider-using-f-string

import os
import traceback
import json
import codecs
import subprocess
import logging

import jsonschema

from PyQt5.QtWidgets import QApplication  # pylint: disable=no-name-in-module

import xmltodict   # pylint: disable=import-error
import magic       # pylint: disable=import-error

from alfa_CR6_backend.globals import (get_encoding, tr_, SCHEMAS_PATH)


class OrderParser:

    mcm_csv_header = 'BASE'
    sikkens_pdf_header = 'Anteprima Formula'
    kcc_pdf_header = "KCC Color Navi Formulation"

    sw_txt_headers = [
        "Intelligent Colour Retrieval & Information Services",
        "Octoral Information Services"
    ]

    def __init__(self, exception_handler=None):
        self.exception_handler = exception_handler

    @staticmethod
    def _substitute_aliases(properties):

        try:
            if QApplication.instance():
                _alias_file = os.path.join(QApplication.instance().settings.DATA_PATH, "pigment_alias.json")
                with open(_alias_file, encoding='UTF-8') as f:
                    alias_dict = json.load(f)

                ingredients = properties.get('ingredients', [])
                for i in ingredients:
                    pigment_name = i["pigment_name"]
                    for k, v in alias_dict.items():
                        if pigment_name in v:
                            i["pigment_name"] = k
                            logging.warning(f"pigment_name:{pigment_name}, k:{k}")
                            properties['meta'].setdefault('alias', [])
                            properties['meta']['alias'].append((pigment_name, k))
                            break

        except Exception as e:  # pylint:disable=broad-except
            logging.error(traceback.format_exc())
            logging.error(f"e:{e}")

        return properties

    @classmethod
    def parse_nro_xml(cls, xml_as_dict):

        properties = {
            "meta": {},
            "ingredients": [],
            "extra_lines_to_print": [],
        }

        if xml_as_dict.get("COLORFORMULA"):
            properties["meta"] = xml_as_dict["COLORFORMULA"]["FORMULA"].copy()

            formulaitem = xml_as_dict["COLORFORMULA"]["FORMULAITEMS"]["FORMULAITEM"].copy()

            properties["ingredients"] = []
            for item in formulaitem:
                properties["ingredients"].append({
                    "pigment_name": item["COLORANT"],
                    "weight(g)": round(float(item["AMOUNT"]), 4),
                    "description": ""
                })

            innercolorcode = properties["meta"].get("INNERCOLORCODE", "")
            brand = properties["meta"].get("BRAND", "")
            product = properties["meta"].get("PRODUCT", "")
            amount = properties["meta"].get("AMOUNT", "")

            properties["extra_lines_to_print"].append(f'{brand}')
            properties["extra_lines_to_print"].append(f'{innercolorcode}')
            properties["extra_lines_to_print"].append(f'{product}, {amount}')

            # ~ logging.warning(json.dumps(formulaitem, indent=2, ensure_ascii=False))

        return properties

    @staticmethod
    def parse_mcm_csv(lines):
        # ~ logging.warning(f"lines:{lines}")
        properties = {
            "meta": {},
            "ingredients": [],
            "extra_lines_to_print": [],
        }

        section = 0
        keys_ = []
        items_ = []
        for l in lines:
            if section == 0:
                if not l.strip():
                    section = 1
                else:
                    toks = l.strip().split(';')
                    if toks[1:]:
                        properties['meta'][toks[0]] = toks[1]
            elif section == 1:
                keys_ = l.split(';')
                section = 2
            elif section == 2:
                vals_ = l.split(';')
                new_item = dict(zip(keys_, vals_))
                items_.append(new_item)

        for item_ in items_:
            if item_['Mischlack']:
                properties["ingredients"].append({
                    "pigment_name": item_['Mischlack'],
                    "weight(g)": round(float(item_['Waage'].replace(",", "")), 4),
                    "description": item_['Name']
                })

        hersteller = properties['meta'].get("Hersteller")
        oem_code = properties['meta'].get("OEM-Code")
        name = properties['meta'].get("Name")
        menge = properties['meta'].get("Menge")
        properties["extra_lines_to_print"].append(f"{hersteller}")
        properties["extra_lines_to_print"].append(f"{oem_code} | {menge}")
        properties["extra_lines_to_print"].append(f"{name}")

        return properties

    @staticmethod
    def parse_sw_txt(lines):       # pylint: disable=too-many-locals

        def __find_items_in_line(items, l):
            return not [i for i in items if i not in l]

        sw_dat_keys_str = """
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

        sw_dat_keys = [s.strip() for s in sw_dat_keys_str.split('\n')]

        sw_dat_start_line_items = [
            "Tinta Base", "Peso"]
        sw_dat_end_line_items = ["Totale"]

        properties = {
            "meta": {},
            "ingredients": [],
        }

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

        marca = properties.get('meta', {}).get('Marca', '')
        codicecolore = properties.get('meta', {}).get('Codicecolore', '')
        secondo_nome = properties.get('meta', {}).get('Secondo-nome', '')
        quantita = properties.get('meta', {}).get('Quantità', '')
        l1 = f"{marca.strip()}"
        l2 = f"{secondo_nome.strip()}"
        l3 = f"{codicecolore.strip()} {quantita.strip()}"
        properties["extra_lines_to_print"] = [l1, l2, l3]

        return properties

    @staticmethod
    def parse_sw_json(content):

        properties = {}

        fname = os.path.join(SCHEMAS_PATH, 'SW_formula_file_schema.json')
        with open(fname, encoding='UTF-8') as fd:
            schema_ = json.load(fd)
            jsonschema.validate(schema_, content)
            properties = content
            for i in properties.get("ingredients"):
                i["pigment_name"] = i.pop("code")

            # TODO: add extra_lines_to_print
            properties["extra_lines_to_print"] = [
            ]

        return properties

    @staticmethod
    def parse_kcc_json(content):

        properties = {}

        properties["meta"] = {}

        for k in [
                "color to compare",
                "basic information",
                "automobile information",
                "color code",
                "total",
                "note"]:
            properties["meta"][k] = content.get(k, "")

        sz = content.get("total", "100")
        sz = "1000" if sz.lower() == "1l" else sz
        properties["size(cc)"] = sz

        properties["ingredients"] = []
        for item in content.get("color information", {}):
            new_item = {}
            new_item["pigment_name"] = item["Color MixingAgen"]
            new_item["description"] = item["Color Mixing Agen Name"]
            new_item["weight(g)"] = round(float(item["weight(g)"]), 4)
            properties["ingredients"].append(new_item)

        properties["extra_lines_to_print"] = []

        color_code_and_multi_name = ""
        if content.get("color code"):
            color_code_and_multi_name += f'{content["color code"]}'
        if content.get("multi name"):
            color_code_and_multi_name += f' {content["multi name"]}'
        if color_code_and_multi_name:
            properties["extra_lines_to_print"].append(color_code_and_multi_name)

        if content.get("total"):
            properties["extra_lines_to_print"].append(f'{ content["total"] }')

        return properties

    @staticmethod
    def parse_kcc_pdf(lines):  # pylint: disable=too-many-locals

        section_separator = "__________________________"
        section = 0
        section_cntr = 0
        meta = {}
        ingredients = []
        extra_info = []
        properties = {}
        for l in lines:

            if not l:
                continue

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

        meta["extra_info"] = extra_info
        properties = {
            "meta": meta,
            "ingredients": ingredients,
            "extra_lines_to_print": [],
        }

        _toks = meta.get("Number", []) and meta["Number"].split(' ')
        _line = (_toks[1] if _toks[1:] else '')
        properties["extra_lines_to_print"].append(f'{_line}')
        properties["meta"]["color code"] = f"{_line}"

        _line = (extra_info[1] if extra_info[1:] else '')
        properties["extra_lines_to_print"].append(f"{_line}")

        # ~ logging.warning(f'properties["extra_lines_to_print"]:{properties["extra_lines_to_print"]}')

        return properties

    @staticmethod
    def parse_sikkens_pdf(lines):     # pylint: disable=too-many-locals, too-many-branches, too-many-statements

        properties = {}
        section = 0
        offset_value = 0
        section_cntr = 0
        meta = {}
        ingredients = []
        extra_info = []
        formula_type = None
        for l in lines:
            if not l:
                continue
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

        meta["extra_info"] = ["\t".join([t.strip() for t in l.split("   ") if t]) for l in extra_info]
        properties = {
            "meta": meta,
            "ingredients": ingredients,
        }

        total_lt = float(properties['meta'][1][1].split(' ')[0])
        total_gr = sum([i["weight(g)"] for i in properties['ingredients']])
        if total_gr < total_lt * 800 or total_gr > total_lt * 1200:
            logging.error(f"total_lt:{total_lt}, total_gr:{total_gr}")
            properties = {}

        t1 = properties.get('meta', {}).get(1, [""])[0]
        t2 = properties.get('meta', {}).get(1, ["", ""])[1]
        t3 = properties.get('meta', {}).get(2, [""])[0]
        t4 = properties.get('meta', {}).get(3, [""])[0]
        properties["extra_lines_to_print"] = [f"{t1}", f"{t2} {t3}", f"{t4}"]
        # ~ logging.warning(f'properties["extra_lines_to_print"]:{properties["extra_lines_to_print"]}')

        return properties

    @classmethod
    def parse_pdf_order(cls, path_to_file, fixed_pitch=5):

        path_to_txt_file = "{0}.txt".format(path_to_file)

        cmd_ = ["pdftotext", "-fixed", f"{fixed_pitch}", path_to_file, path_to_txt_file]
        # ~ logging.warning(f"cmd_:{cmd_}")

        subprocess.run(cmd_, check=False)
        e = get_encoding(path_to_txt_file)

        properties = {}

        with codecs.open(path_to_txt_file, encoding=e) as fd:
            lines = [l.strip() for l in fd.readlines()]

        if cls.sikkens_pdf_header in lines[0]:
            properties = cls.parse_sikkens_pdf(lines)

            if properties.get('meta'):
                properties['meta']['header'] = cls.sikkens_pdf_header

        elif cls.kcc_pdf_header.split(' ') == [t.strip() for t in lines[0].split(' ') if t]:
            properties = cls.parse_kcc_pdf(lines)

            if properties.get('meta'):
                properties['meta']['header'] = cls.kcc_pdf_header

        cmd_ = f'rm -f "{path_to_txt_file}"'
        # ~ logg    ing.warning(f"cmd_:{cmd_}")
        os.system(cmd_)

        return properties

    @classmethod
    def parse_xml_order(cls, path_to_file):  # pylint: disable=too-many-locals

        properties = {}

        e = get_encoding(path_to_file)
        with codecs.open(path_to_file, encoding=e) as fd:
            xml_as_dict = xmltodict.parse(fd.read(), encoding=e)

            properties = cls.parse_nro_xml(xml_as_dict)

        if properties.get('meta'):
            properties['meta']['header'] = 'nro_xml'

        return properties

    @classmethod
    def parse_txt_order(cls, path_to_file):  # pylint: disable=too-many-locals

        properties = {}
        lines = []

        e = get_encoding(path_to_file)
        with codecs.open(path_to_file, encoding=e) as fd:
            lines = fd.readlines()

        if [_hdr for _hdr in cls.sw_txt_headers if _hdr in lines[0]]:

            header = lines[0].strip()
            properties = cls.parse_sw_txt(lines)

            if properties.get('meta') is not None:
                properties['meta']['header'] = header

        elif cls.mcm_csv_header in lines[0]:
            properties = cls.parse_mcm_csv(lines)

            if properties.get('meta') is not None:
                properties['meta']['header'] = cls.mcm_csv_header

        return properties

    @classmethod
    def parse_json_order(cls, path_to_file):

        properties = {}

        e = get_encoding(path_to_file)
        with codecs.open(path_to_file, encoding=e) as fd:
            content = json.load(fd)
            if content.get("header") == "SW CRx formula file":
                properties = cls.parse_sw_json(content)
                properties['meta']['header'] = content['header']
            else:
                properties = cls.parse_kcc_json(content)
                if properties.get('meta'):
                    properties['meta']['header'] = 'kcc_json'

        return properties

    def parse(self, path_to_file):

        mime = magic.Magic(mime=True)
        mime_type = mime.from_file(path_to_file)
        # ~ logging.warning(f"path_to_file:{path_to_file}, mime_type:{mime_type}")

        properties = {}

        try:
            if mime_type == 'application/json':
                properties = self.parse_json_order(path_to_file)

            elif mime_type == 'application/pdf':
                for fp in (0, 5):
                    try:
                        # ~ logging.warning(f"trying fp:{fp} ...")
                        properties = self.parse_pdf_order(path_to_file, fp)
                        if properties.get('ingredients'):
                            break
                    except Exception as e:              # pylint: disable=broad-except
                        logging.warning(e)

            elif mime_type == 'text/plain':
                properties = self.parse_txt_order(path_to_file)
            elif mime_type == 'text/xml':
                properties = self.parse_xml_order(path_to_file)
            else:
                raise Exception(f"unknown mime_type:{mime_type} for file:{path_to_file}")

            if properties.get('meta'):
                properties['meta']['file name'] = os.path.split(path_to_file)[1]

                properties = self._substitute_aliases(properties)

            err_msg = tr_("properties not valid:{}").format(properties)[:400]
            assert properties.get('meta') is not None, err_msg
            assert not properties['meta'].get('error'), err_msg

        except Exception as e:              # pylint: disable=broad-except

            logging.error(f"format error in file:{path_to_file}")
            logging.error(traceback.format_exc())

            msg = tr_("format error in file:{} \n {}").format(path_to_file, e)

            properties.setdefault("meta", {})
            properties['meta']['error'] = msg

            # ~ e = get_encoding(path_to_file)
            with codecs.open(path_to_file, 'rb') as fd:
                file_content = fd.read()[:10000]
                properties['meta']['file_content'] = str(file_content)

            if self.exception_handler:
                self.exception_handler(msg)

        return properties
