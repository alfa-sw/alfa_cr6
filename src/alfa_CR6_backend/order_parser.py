# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name
# pylint: disable=too-many-lines
# pylint: disable=logging-fstring-interpolation, consider-using-f-string

import os
import traceback
import json
import codecs
import subprocess
import logging
import copy
import time
import configparser
import re

import jsonschema

import xmltodict   # pylint: disable=import-error
import magic       # pylint: disable=import-error

from alfa_CR6_backend.globals import (get_encoding, tr_, SCHEMAS_PATH, get_application_instance)


def get_specific_weights():

    ret_dict = {}
    try:
        _app = get_application_instance()
        for m in _app.machine_head_dict.values():
            if m:
                for p in m.pigment_list:
                    p_name = p['name']
                    p_specific_weight = m.get_specific_weight(p_name)
                    ret_dict[p_name] = p_specific_weight if p_specific_weight > 0.001 else 1.0

        logging.warning(f"ret_dict:{ret_dict}")
    except Exception as e:  # pylint: disable=broad-except
        logging.warning(f"e:{e}")

    return ret_dict


def replace_invalid_tags(path_to_file):

    TAGS_TO_FIX = {
        "<Total Price>": "<Total_Price>",
        "</Total Price>": "</Total_Price>",
        "<Real Weight>": "<Real_Weight>",
        "</Real Weight>": "</Real_Weight>",
    }

    try:
        e = get_encoding(path_to_file)
        with codecs.open(path_to_file, encoding=e) as fd:
            data = fd.read()
            for k, v in TAGS_TO_FIX.items():
                data = data.replace(k, v)

        with codecs.open(path_to_file, 'w', encoding=e) as fd:
            fd.write(data)

    except Exception as e:  # pylint:disable=broad-except
        logging.error(traceback.format_exc())
        logging.error(f"e:{e}")


class OrderParser:       # pylint: disable=too-many-public-methods

    mcm_csv_header = 'BASE'
    sikkens_pdf_header = 'Anteprima Formula'
    kcc_pdf_header = "KCC Color Navi Formulation"
    cpl_pdf_header = "MixingSys"
    DICHEMIX_pdf_header = "Dichemix"
    mixcar_pdf_header = "Rapport de formule"
    axalta_pdf_headers = ["Axalta Industrial", "Cromax", "Standox"]  # duthoo, Gteam, Serwind/Autocolor
    codevid_pdf_header = "Formula Details"          # duthoo
    basf_1_pdf_header = "Base Target Amt. CumAmt."  # BASF Refinty
    basf_2_pdf_headers = ["Base Amount", "Ingredients Kontrolle"]  # BASF Cosima
    carcolour_pdf_footer = 'PPG Industries, Inc. PPG CONFIDENTIAL INFORMATION'

    sw_txt_headers = [
        "Intelligent Colour Retrieval & Information Services",
        "Octoral Information Services"
    ]

    def __init__(self, exception_handler=None):
        self.exception_handler = exception_handler

    @staticmethod
    def _substitute_aliases(properties):

        try:
            _app = get_application_instance()
            if _app:
                _alias_file = os.path.join(_app.settings.DATA_PATH, "pigment_alias.json")
            else:
                _alias_file = "/opt/alfa_cr6/data/pigment_alias.json"

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

        properties["meta"] = xml_as_dict["COLORFORMULA"]["FORMULA"].copy()

        formulaitem = xml_as_dict["COLORFORMULA"]["FORMULAITEMS"]["FORMULAITEM"].copy()

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

    @classmethod
    def parse_Besa_SINNEK_xml(cls, xml_as_dict):

        # ~ logging.warning(json.dumps(xml_as_dict, indent=2, ensure_ascii=False))

        properties = {
            "meta": {},
            "ingredients": [],
            "extra_lines_to_print": [],
        }

        properties["meta"] = xml_as_dict["Table"]["OT"].copy()

        componente = xml_as_dict["Table"]["Componentes"]["Componente"].copy()
        if not isinstance(componente, list):
            componente = [componente, ]

        for item in componente:
            properties["ingredients"].append({
                "pigment_name": item["Codigo"],
                "weight(g)": round(float(item["Gramos"]), 5),
                "description": item.get("Descripcion", '')
            })

        info_to_print = {}
        for k in (
                'Fabricante',
                'ColorCode',
                'Color',
                'RealWeight',
                'Calidad',
                'Work'):
            info_to_print[k] = properties["meta"].get(k, None) or ''

        fmt_ = """{Fabricante}
{ColorCode} - {Color}
{Calidad}
weight:{RealWeight}
{Work}"""

        logging.warning(f"info_to_print:{info_to_print}")

        properties["extra_lines_to_print"] = [s[:18] for s in fmt_.format(**info_to_print).split('\n')]

        return properties

    @classmethod
    def parse_MIXIT_xml(cls, xml_as_dict):

        properties = {
            "meta": {},
            "ingredients": [],
            "extra_lines_to_print": [],
        }

        properties["meta"] = xml_as_dict["ColorFormula"].copy()

        information = xml_as_dict["ColorFormula"]["Information"].copy()
        brand = information.get("Brand", '.')
        description = information.get("Description", '.')
        AKZOCode = information.get("AKZOCode", '.')

        CurrentFormula = xml_as_dict["ColorFormula"]["CurrentFormula"].copy()
        amount = CurrentFormula.get("Amount", '.')
        typeOfUnit = CurrentFormula.get("TypeOfUnit", '')

        # ~ productItem = xml_as_dict["ColorFormula"]["Products"]["ProductItem"].copy()
        # ~ name = productItem.get("Name", '.')

        properties["extra_lines_to_print"].append(f'{brand}')
        properties["extra_lines_to_print"].append(f'{description}')
        properties["extra_lines_to_print"].append(f'"{AKZOCode}" {amount}({typeOfUnit})')

        formulaRecipeItem = xml_as_dict["ColorFormula"]["FormulaRecipe"]["FormulaRecipeItem"].copy()

        for item in formulaRecipeItem:
            properties["ingredients"].append({
                "pigment_name": item["Colorant"],
                "weight(g)": round(float(item["Absolute"]), 5),
                "description": ""
            })

        # ~ logging.warning(json.dumps(formulaRecipeItem, indent=2, ensure_ascii=False))

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

        content = copy.deepcopy(content)

        properties = {}

        fname = os.path.join(SCHEMAS_PATH, 'SW_formula_file_schema.json')
        with open(fname, encoding='UTF-8') as fd:
            schema_ = json.load(fd)
            jsonschema.validate(schema_, content)
            properties = content
            for i in properties.get("ingredients", []):
                if i.get("code") is not None:
                    i["pigment_name"] = i.pop("code")
                i["weight(g)"] = round(float(i["weight(g)"]), 4)

            batchId = properties.get("batchId", '')
            meta = properties.get("meta", {})
            meta["batchId"] = batchId
            brand = meta.get("brand", '')
            quality = meta.get("quality", '')
            colorCode = meta.get("colorCode", '')
            variantCode = meta.get("variantCode", '')
            colorName = meta.get("colorName", '')
            qtty = meta.get("quantity(l)")
            if qtty is None:
                qtty = meta.get("quantity", 0)
            quantity = round(float(qtty), 3)
            qty_uom = meta.get("quantityUom", '').upper()
            date_time = str(time.asctime())

            if properties.get("extra_lines_to_print") is None:
                printable_extra_lines = [
                    f"{brand} - {quality}",
                    f"{colorCode} - {variantCode}",
                    f"{quantity} {qty_uom} {colorName}",
                    f"{batchId}",
                    f"{date_time}"
                ]

                job_id_value = properties.get("jobId", "")
                if job_id_value:
                    printable_extra_lines.insert(0, job_id_value)

                properties["extra_lines_to_print"] = printable_extra_lines

        logging.info(f"properties:{properties}")
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
    def parse_akzo_azure_json(content):

        properties = {}
        unit = content['mix']['shotUnit']
        properties['extra_lines_to_print'] = []
        properties['meta'] = {
            'canVolume': content['canVolume'],
            'status': content['status'],
            'shotUnit': unit,
            'mixName': content['mix']['name'],
            'productName': content['mix']['productName'],
            'id': content['id']
        }

        if unit != "gram":
            properties['meta']['error'] = "unit is not gram"

        ingredients = []
        total_amount = 0.
        for i in content['mix']['components']:
            ingr = {}
            if i.get("code") is not None:
                ingr["pigment_name"] = i.get("code")
                ingr["description"] = i.get("description")
                amount = round(float(i.get("desiredAmount")), 4)
                ingr["weight(g)"] = amount
                ingredients.append(ingr)
                total_amount = total_amount + amount

        properties["extra_lines_to_print"] = [
            properties['meta']['productName'],
            properties['meta']['mixName'],
            f'{total_amount}({unit})'
        ]
        properties["ingredients"] = ingredients
        return properties

    @staticmethod
    def parse_cpl_pdf(lines):  # pylint: disable=too-many-locals

        properties = {}
        meta = {}

        keys_0 = ['Make', 'Color description', 'Color code', 'Tone', 'Type', 'Years']
        keys_1 = ['Code', 'Description', 'Weights', 'Cumul']

        lines_ = [l for l in lines if l]

        positions = [lines_[2].find(k) for k in keys_0] + [len(lines_[2])]
        vals = []
        for p1, p2 in zip(positions[:-1], positions[1:]):
            val = lines_[3][p1:p2].strip()
            vals.append(val)
        meta = dict(zip(keys_0, vals))

        section = 0
        ingreds = []
        for l in lines_[4:]:
            toks = [t.strip() for t in l.split("  ") if t.strip()]
            if section == 0:
                if "Formula date:" in l and "Panel:" in l:
                    meta['Panel'] = [t.strip() for t in l.split("Panel:")[1].split(' ') if t.strip()][0]
                    section = 1
            elif section == 1:
                if "Color Box info" in l:
                    meta['quantity'] = f"{toks[0].split(' ')[0]} LITERS"
                    section = 2
            elif section == 2:
                s0 = {i.strip() for i in toks}
                s1 = set(keys_1)
                s2 = s0.intersection(s1)
                if len(s2) == len(keys_1):
                    section = 3
            elif section == 3:
                if "Alternative descriptions" in l:
                    section = 4
                else:
                    item = dict(zip(keys_1, toks))
                    item["pigment_name"] = item.pop("Code")
                    item["weight(g)"] = round(float(item.pop("Weights")), 4)
                    item["description"] = item.pop("Description")
                    item.pop("Cumul")
                    ingreds.append(item)

        properties["meta"] = meta
        properties["ingredients"] = ingreds

        # ~ -Make -Color description -Color code -Type -Panel -Liters
        properties["extra_lines_to_print"] = [
            meta.get('Color description', ''),
            f"{meta.get('Make', '')}; {meta.get('Color code', '')}",
            f"{meta.get('Type', '')}; {meta.get('quantity', '')}; {meta.get('Panel', '')}",
        ]

        return properties

    @staticmethod
    def parse_kcc_pdf(lines, second_coat=False):  # pylint: disable=too-many-locals, too-many-branches, too-many-statements

        section_separator = "__________________________"
        section = 0
        section_cntr = 0
        meta = {}
        ingredients = []
        extra_info = []
        properties = {}
        is_double_coat = False

        double_coat_tag = ''

        for l in lines:

            if not l:
                continue

            if not second_coat and ('SECOND' in l and 'COAT' in l):
                is_double_coat = True
                double_coat_tag = 'FIRST COAT'
                continue

            if second_coat and ('SECOND' in l and 'COAT' in l):
                second_coat = False
                double_coat_tag = 'SECOND COAT'

            if section_separator in l:
                if not second_coat:
                    section += 1
                    section_cntr = 0
            else:
                if section == 0:
                    toks = [t_ for t_ in [t.strip() for t in l.split(":")] if t_]
                    if len(toks) == 2:
                        meta[toks[0]] = toks[1]
                elif section == 1:
                    toks = [t_ for t_ in [t.strip() for t in l.split(":")] if t_]
                    description = toks[0]
                    sub_toks = []
                    for t in toks[1].split("      "):
                        if t.strip():
                            sub_toks.append(t.strip())
                    # ~ logging.warning(f'sub_toks:{sub_toks}')
                    if len(sub_toks) == 2:
                        name, val = sub_toks[0], sub_toks[1]
                        value = round(float(val.split('(G)')[0]), 4)
                        new_item = {}
                        name = ' '.join(name.split())
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

        _toks = meta.get("Number", []) and meta["Number"].split()
        _line = (_toks[1] if _toks[1:] else '')
        properties["meta"]["color code"] = f"{_line}"

        properties["extra_lines_to_print"].append(f'{_line}')

        _line = (extra_info[1] if extra_info[1:] else '')
        _line = " ".join([t.strip() for t in _line.split(" ") if t.strip()])
        properties["extra_lines_to_print"].append(f"{_line}")

        if double_coat_tag:
            properties["extra_lines_to_print"].append(tr_(double_coat_tag))
            properties["meta"]["extra_info"].append(double_coat_tag)

        # ~ logging.warning(f'properties["extra_lines_to_print"]:{properties["extra_lines_to_print"]}')

        return properties, is_double_coat

    @staticmethod
    def parse_mixcar_pdf(lines):  # pylint: disable=too-many-locals, too-many-branches, too-many-statements

        def parse_ingredient_line(l):

            ingredient = None
            toks = l.split()
            if len(toks) > 2:

                value = float(toks[-2])
                name = toks[0]
                description = " ".join(toks[1:-2])

                ingredient = {
                    "pigment_name": name,
                    "weight(g)": round(value, 4),
                    "description": description
                }

            return ingredient

        head_section_0 = "Rapport de formule"
        head_section_1 = "REF Description"
        head_section_2 = "CONFIDENTIAL INFORMATION"
        section_cntr = 0
        properties = {}
        ingredients = []
        extra_info = []

        for l in lines:

            if not l:
                continue

            l = " ".join(l.split())

            if head_section_0 in l:
                section_cntr = 0
                continue
            if head_section_1 in l:
                section_cntr = 1
                continue
            if head_section_2 in l:
                section_cntr = 2
                continue

            if section_cntr == 0:
                extra_info.append(l)
                continue

            if section_cntr == 1:
                ingredient = parse_ingredient_line(l)
                if ingredient:
                    ingredients.append(ingredient)

                continue

            if section_cntr == 2:
                break

        properties['ingredients'] = ingredients
        properties['meta'] = {'extra_info': extra_info}

        return properties

    @staticmethod
    def parse_axalta_pdf(original_lines):  # pylint: disable=too-many-locals, too-many-branches, too-many-statements

        def parse_ingredient_line(l):

            ingredient = None
            l = l.replace(',', '.')
            toks = [t.strip() for t in l.split('  ')]
            toks = [t for t in toks if t]
            # ~ logging.error(f"l:{l}, toks:{toks}")
            if len(toks) >= 5 and toks[0].isdigit() and toks[-1].replace('.',
                                                                         '', 1).isdigit() and toks[-2].replace('.', '', 1).isdigit():

                value = float(toks[-2])
                name = toks[1]
                description = " ".join(toks[2:-2])

                ingredient = {
                    "pigment_name": name,
                    "weight(g)": round(value, 4),
                    "description": description
                }

            # ~ logging.error(f"toks:{toks}, ingredient:{ingredient}")

            return ingredient

        properties = {}
        ingredients = []
        extra_info = []
        extra_lines_to_print = []

        for l in original_lines:

            if "Page 1" in l:
                break

            if not l:
                continue

            ingredient = parse_ingredient_line(l)
            # ~ logging.error(f"l:{l}")
            if ingredient:
                ingredients.append(ingredient)
            else:

                l = " ".join(l.split())

                if l.strip():

                    if extra_info and [k for k in ["register",
                                                   "codice colore produttore",
                                                   "kód farby výrobcu",
                                                   "manufacturer colour code",
                                                   "výrobní kód barvy"] if k in extra_info[-1].lower()]:
                        toks = l.split()
                        # ~ logging.error(f"l:{l}, toks:{toks}")
                        if toks:
                            extra_lines_to_print.append(" ".join(toks[:-1]))

                    elif extra_info and [k for k in ["kleurcode fabrikant",
                                                     "nome colore produttore",
                                                     "názov farby výrobcu",
                                                     "manufacturer colour name",
                                                     "výrobní jméno barvy"] if k in extra_info[-1].lower()]:
                        toks = l.split()
                        # ~ logging.error(f"l:{l}, toks:{toks}")
                        if toks:
                            extra_lines_to_print.append(" ".join(toks[:-2]))

                    extra_info.append(l)

        properties['extra_lines_to_print'] = extra_lines_to_print
        properties['ingredients'] = ingredients
        properties['meta'] = {'extra_info': extra_info}

        return properties

    @staticmethod
    def parse_axalta_pdf_OLD(lines):  # pylint: disable=too-many-locals, too-many-branches, too-many-statements

        def parse_ingredient_line(l):

            ingredient = None
            toks = l.split()
            if len(toks) > 2:

                value = float(toks[-2].replace(',', '.'))
                name = toks[1]
                description = " ".join(toks[2:-2])

                ingredient = {
                    "pigment_name": name,
                    "weight(g)": round(value, 4),
                    "description": description
                }

            return ingredient

        head_section_0 = "Axalta Industrial"
        head_section_1 = "Productcode Omschrijving"
        head_section_2 = "Totaal"
        section_cntr = 0
        properties = {}
        ingredients = []
        extra_info = []
        extra_lines_to_print = []

        for l in lines:

            if not l:
                continue

            l = " ".join(l.split())

            if head_section_0 in l:
                section_cntr = 0
                continue
            if head_section_1 in l:
                section_cntr = 1
                continue
            if head_section_2 in l:
                section_cntr = 2
                continue

            if section_cntr == 0:

                if extra_info and "register" in extra_info[-1].lower():
                    toks = l.split()
                    if toks:
                        extra_lines_to_print.append(toks[-2])
                if extra_info and extra_info[-1].lower().startswith("kleurcode fabrikant"):
                    toks = l.split()
                    if toks:
                        extra_lines_to_print.append(" ".join(toks[:-2]))
                # ~ if extra_info and "laag" in extra_info[-1].lower():
                    # ~ toks = l.split()
                    # ~ if toks:
                        # ~ extra_lines_to_print.append(toks[-1])

                extra_info.append(l)
                continue

            if section_cntr == 1:
                ingredient = parse_ingredient_line(l)
                if ingredient:
                    ingredients.append(ingredient)

                continue

            if section_cntr == 2:
                extra_info.append(l)
                if "hoeveelheid" in l.lower():
                    toks = l.split()
                    if toks:
                        extra_lines_to_print.append(" ".join(toks[1:]))

        properties['extra_lines_to_print'] = extra_lines_to_print
        properties['ingredients'] = ingredients
        properties['meta'] = {'extra_info': extra_info}

        return properties

    @classmethod
    def parse_codevid_txt(cls, lines):  # pylint: disable=too-many-locals, too-many-branches, too-many-statements
        new_lines = []
        start = 0
        for l in lines:

            # ~ logging.warning(f"l:{l}")

            if cls.codevid_pdf_header in l:
                start = 1

            if start:
                toks = [t.strip() for t in l.split(",")]
                toks = [t.lstrip('"') for t in toks]
                toks = [t.rstrip('"') for t in toks]
                toks = [t.ljust(30) for t in toks]
                new_l = " ".join(toks)
                # ~ logging.warning(f"new_l:{new_l}")
                new_lines.append(new_l)

        # ~ logging.warning(f"new_lines:{new_lines}")

        return cls.parse_codevid_pdf(new_lines)

    @staticmethod
    def parse_codevid_pdf(lines):  # pylint: disable=too-many-locals, too-many-branches, too-many-statements

        def parse_ingredient_line(l):

            ingredient = None
            toks = l.split()
            if len(toks) > 2:

                value = float(toks[-2].replace(',', '.'))
                name = toks[0]
                description = " ".join(toks[1:-2])

                ingredient = {
                    "pigment_name": name,
                    "weight(g)": round(value, 4),
                    "description": description
                }

            return ingredient

        head_section_0 = "Formula Details"
        head_section_1 = "Colour Number"
        colour_number_index = -1
        colour_name_index = -1
        # ~ head_section_2 = "Customer"
        head_section_2 = "Manufacturer"
        head_section_3 = "Formula"
        section_cntr = 0
        properties = {}
        ingredients = []
        extra_info = []
        extra_lines_to_print = []
        section_2_extra_lines_to_print = [[], []]

        for l in lines:

            if not l:
                continue

            if head_section_0 in l:
                section_cntr = 0
                continue
            if head_section_1 in l:
                section_cntr = 1
                colour_number_index = l.find(head_section_1)
                colour_name_index = l.find("Colour Name")
                continue
            if head_section_2 in l:
                section_cntr = 2
                continue
            if head_section_3 in l:
                section_cntr = 3
                continue

            if section_cntr == 0:

                l = " ".join(l.split())
                extra_info.append(l)
                continue

            if section_cntr == 1:

                col_number = l[colour_number_index:].strip()
                if col_number:
                    section_2_extra_lines_to_print[0].append(col_number)
                col_name = l[colour_name_index:colour_name_index + 25].strip()
                if col_name:
                    section_2_extra_lines_to_print[1].append(col_name)
                    # ~ logging.warning(f"col_name:{col_name}, l:{l}")

            if section_cntr == 2:

                l = " ".join(l.split())
                extra_info.append(l)
                continue

            if section_cntr == 3:

                l = " ".join(l.split())
                ingredient = parse_ingredient_line(l)
                if ingredient:
                    ingredients.append(ingredient)
                else:
                    if extra_info and "quantity" in extra_info[-1].lower():
                        extra_lines_to_print.append(l)
                    extra_info.append(l)

                continue

        properties['extra_lines_to_print'] = [" ".join(l)
                                              for l in section_2_extra_lines_to_print] + extra_lines_to_print
        properties['ingredients'] = ingredients
        properties['meta'] = {'extra_info': extra_info}

        return properties

    @staticmethod
    def parse_sikkens_pdf(lines):     # pylint: disable=too-many-locals, too-many-branches, too-many-statements

        _specific_weights = get_specific_weights()

        properties = {}
        section = 0
        offset_value = 0
        section_cntr = 0
        head_section = []
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
                        # ~ meta[section_cntr - 3] = [t.strip() for t in l.split("   ") if t]
                        head_section.append(l)
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

        meta = {k: l.split() for k, l in enumerate(head_section)}
        meta["extra_info"] = ["\t".join(l.split()) for l in extra_info]
        properties = {
            "meta": meta,
            "ingredients": ingredients,
        }

        total_lt = 0.
        for i in head_section[0].split():
            try:
                total_lt = float(i)
                break
            except Exception:  # pylint: disable=broad-except
                pass

        if total_lt > 0.00001:
            # ~ total_gr = sum([i["weight(g)"] for i in properties['ingredients']])
            # ~ if total_gr < total_lt * 800 or total_gr > total_lt * 1200:
            # ~ err = f"total_lt:{total_lt}, total_gr:{total_gr}"
            # ~ logging.error(err)
            # ~ properties = {'error': err}
            total_vol_cc = sum([
                (i["weight(g)"] / _specific_weights.get(i["pigment_name"], 1.5)) for i in properties['ingredients']
            ])
            total_vol_cc = round(total_vol_cc, 3)

            if total_vol_cc > total_lt * 1050:
                err = f"total_lt:{total_lt}, total_vol_cc:{total_vol_cc}"
                logging.error(err)
                properties = {'error': err}

        extra_lines_to_print = []
        try:
            extra_lines_to_print.append(' '.join(head_section[0].split()[:-2]))
            extra_lines_to_print.append(' '.join(head_section[0].split()[-2:]))
            extra_lines_to_print.append(' '.join(head_section[1].split()[:-1]))
            extra_lines_to_print.append(' '.join(head_section[2].split()[:-3]))
        except Exception:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())

        properties["extra_lines_to_print"] = extra_lines_to_print

        return properties

    @staticmethod
    def parse_basf_1_pdf(original_lines):

        def parse_ingredient_line(l):

            ingredient = None
            toks = l.split()
            if len(toks) > 2:

                value = float(toks[1].replace(',', '.'))
                name = toks[0]
                description = "."

                ingredient = {
                    "pigment_name": name,
                    "weight(g)": round(value, 4),
                    "description": description
                }

            return ingredient

        head_section_1 = "Base Target Amt. CumAmt."
        head_section_2 = "Optional Greyshade"

        section_cntr = 0
        properties = {}
        ingredients = []
        extra_info = []

        for l in original_lines:

            if not l:
                continue

            if head_section_1 in ' '.join(l.split()):
                section_cntr = 1
            elif head_section_2 in l:
                section_cntr = 2
            else:

                if section_cntr == 0:

                    l = " ".join(l.split())
                    extra_info.append(l)

                elif section_cntr == 1:

                    l = " ".join(l.split())
                    ingredient = parse_ingredient_line(l)
                    if ingredient:
                        ingredients.append(ingredient)
                    else:
                        extra_info.append(l)

                elif section_cntr == 2:

                    l = " ".join(l.split())
                    extra_info.append(l)

        # ~ properties['extra_lines_to_print'] = extra_lines_to_print
        properties['extra_lines_to_print'] = [l for l in extra_info if l and len(l) < 30 and "Suffix" not in l]
        properties['ingredients'] = ingredients
        properties['meta'] = {'extra_info': extra_info}

        return properties

    @staticmethod
    def parse_basf_2_pdf(original_lines):

        def parse_ingredient_line(l):

            ingredient = None
            toks = l.split()
            if len(toks) >= 2:

                value = float(toks[1].replace(',', '.'))
                name = toks[0]
                description = "."

                ingredient = {
                    "pigment_name": name,
                    "weight(g)": round(value, 4),
                    "description": description
                }

            logging.debug(f"l:{l}, ingredient:{ingredient}")

            return ingredient

        # ~ head_section_1 = "Base Amount"
        # ~ head_section_2 = "total Amount"
        heads_section_1 = ["Base Amount", "Ingredients Kontrolle"]
        heads_section_2 = ["total Amount", "Summe"]

        section_cntr = 0
        properties = {}
        ingredients = []
        extra_info = []

        for l in original_lines:

            if not l:
                continue

            # ~ if head_section_1 in ' '.join(l.split()):
            if [h for h in heads_section_1 if h in ' '.join(l.split())]:
                section_cntr = 1
            # ~ elif head_section_2 in ' '.join(l.split()):
            elif [h for h in heads_section_2 if h in ' '.join(l.split())]:
                section_cntr = 2
                extra_info.append(" ".join(l.split()))
            else:

                if section_cntr == 0:

                    l = " ".join(l.split())
                    extra_info.append(l)

                elif section_cntr == 1:

                    l = " ".join(l.split())
                    ingredient = parse_ingredient_line(l)
                    if ingredient:
                        ingredients.append(ingredient)
                    else:
                        extra_info.append(l)

                elif section_cntr == 2:

                    l = " ".join(l.split())
                    extra_info.append(l)

        # ~ properties['extra_lines_to_print'] = extra_lines_to_print
        properties['extra_lines_to_print'] = [l for l in extra_info if l and len(l) < 30]
        properties['ingredients'] = ingredients
        properties['meta'] = {'extra_info': extra_info}

        return properties

    @staticmethod
    def parse_carcolour_pdf(lines):

        properties = {
            'meta': {},
            'ingredients': [],
            'extra_lines_to_print': {}
        }

        ingredient_pattern = re.compile(r'(\S+)\s+(.+?)\s+(\d+\.\d*)\s+(\d+\.\d*)')

        def extract_meta(line):
            meta_patterns = {
                'Date': r'Date: (.*?) Job No.:',
                'Manufacturer': r'Manufacturer : (.*)',
                'OEM Code': r'OEM Code : (.*?)(?:\s{2,}|$|Brand Code :)',
                'Brand Code': r'Brand Code : (.*)',
                'Description': r'Description : (.*)',
                'Variant': r'Variant : (.*?)(?:\s{2,}|$|Finish Effect :)',
                'Finish Effect': r'Finish Effect : (.*)',
                'Mixing Scheme': r'Mixing Scheme : (.*)',
                'Makes': r'Makes : (.*)'
            }
            meta = {}
            for key, pattern in meta_patterns.items():
                match = re.search(pattern, line)
                if match:
                    meta_key = key.lower().replace(" ", "_")
                    value = match.group(1).strip()
                    if meta_key == 'date':  # Gestione specifica per la data
                        value = re.sub(r'\s{2,}', ' ', value)  # Rimuove spazi multipli
                    if meta_key == 'oem_code':
                        value = value.split(',')[0].strip()
                    meta[meta_key] = value
            return meta

        for line in lines:
            meta_data = extract_meta(line)
            if meta_data:
                properties['meta'].update(meta_data)

        def extract_ingredient_lines(lines):
            start = False
            for line in lines:
                if line.startswith("SKU"):
                    start = True
                    continue
                if line.startswith("Comments"):
                    break
                if start:
                    yield line

        for line in extract_ingredient_lines(lines):
            match = ingredient_pattern.match(line)
            if not match:
                logging.error(f"line: {line} not match ({match}) the ingredient_pattern")
                continue

            code, description, incremental, cumulative = match.groups()
            ingredient = {
                "pigment_name": code,
                "weight(g)": round(float(incremental), 4),
                "description": description.strip()
            }
            properties['ingredients'].append(ingredient)

        properties['extra_lines_to_print'] = [
            f"{properties.get('meta').get('date', '')} - {properties.get('meta').get('makes', '')}",
            f"OEM Code: {properties.get('meta').get('oem_code', '')}",
            f"{properties.get('meta').get('brand_code', '')} - {properties.get('meta').get('manufacturer', '')}",
            f"{properties.get('meta').get('description', '')}",
            f"{properties.get('meta').get('mixing_scheme', '')}",
            f"{properties.get('meta').get('variant', '')} - {properties.get('meta').get('finish_effect', '')}",
        ]

        logging.warning(properties)
        return properties

    @classmethod
    def parse_pdf_order(cls, path_to_file, fixed_pitch=5):  # pylint: disable=too-many-branches, too-many-statements

        path_to_txt_file = "{0}.txt".format(path_to_file)

        if fixed_pitch is None:
            cmd_ = ["pdftotext", "-layout", path_to_file, path_to_txt_file]
        else:
            cmd_ = ["pdftotext", "-fixed", f"{fixed_pitch}", path_to_file, path_to_txt_file]

        subprocess.run(cmd_, check=False)
        e = get_encoding(path_to_txt_file)

        properties = {}

        with codecs.open(path_to_txt_file, encoding=e) as fd:
            original_lines = list(fd.readlines())
            lines = [l.strip() for l in original_lines]
            lines = [l for l in lines if l]

        if cls.sikkens_pdf_header in lines[0]:
            properties = cls.parse_sikkens_pdf(lines)

            if properties.get('meta'):
                properties['meta']['header'] = cls.sikkens_pdf_header

        elif cls.kcc_pdf_header.split(' ') == [t.strip() for t in lines[0].split(' ') if t]:

            prop, second_coat = cls.parse_kcc_pdf(lines)
            properties = [prop, ]
            if second_coat:
                prop, _ = cls.parse_kcc_pdf(lines, second_coat)
                properties.append(prop)

            for p in properties:
                if p.get('meta'):
                    p['meta']['header'] = cls.kcc_pdf_header

        elif cls.cpl_pdf_header in " ".join(lines[0:1]):
            properties = cls.parse_cpl_pdf(lines)

            if properties.get('meta'):
                properties['meta']['header'] = cls.cpl_pdf_header

        elif cls.DICHEMIX_pdf_header in lines[0]:
            properties = cls.parse_cpl_pdf(lines)

            if properties.get('meta'):
                properties['meta']['header'] = cls.DICHEMIX_pdf_header

        elif cls.mixcar_pdf_header in lines[0]:
            properties = cls.parse_mixcar_pdf(lines)

            if properties.get('meta'):
                properties['meta']['header'] = cls.mixcar_pdf_header

        elif [h for h in cls.axalta_pdf_headers if h in " ".join(lines[0:10])]:

            properties = cls.parse_axalta_pdf(original_lines)

            if properties.get('meta'):
                properties['meta']['header'] = [h for h in cls.axalta_pdf_headers if h in " ".join(lines[0:10])][0]

        elif cls.codevid_pdf_header in " ".join(lines[0:1]):
            properties = cls.parse_codevid_pdf(original_lines)

            if properties.get('meta'):
                properties['meta']['header'] = cls.codevid_pdf_header

        elif [l for l in lines if cls.basf_1_pdf_header in ' '.join(l.split())]:

            properties = cls.parse_basf_1_pdf(original_lines)

            if properties.get('meta'):
                properties['meta']['header'] = cls.basf_1_pdf_header

        # ~ elif [l for l in lines if cls.basf_2_pdf_header in ' '.join(l.split())]:
        elif [h for h in cls.basf_2_pdf_headers if h in [' '.join(l.split()) for l in lines]]:

            properties = cls.parse_basf_2_pdf(original_lines)

            if properties.get('meta'):
                properties['meta']['header'] = [
                    h for h in cls.basf_2_pdf_headers if h in ' '.join([' '.join(l.split()) for l in lines])]

        elif cls.carcolour_pdf_footer in lines[-1]:
            properties = cls.parse_carcolour_pdf(lines)

        cmd_ = f'rm -f "{path_to_txt_file}"'
        # ~ logging.warning(f"cmd_:{cmd_}")
        os.system(cmd_)

        ret = properties if isinstance(properties, list) else [properties, ]

        return ret

    @staticmethod
    def parse_palini_ini_order(config):

        logging.warning(f"config:{config}")

        filtered_headers = ["tintacliente", "codtinta", "destinta"]

        properties = {}
        ingredients = []
        extra_info = []
        extra_lines_to_print = []

        for k, v in config.items():

            toks = k.split("COMP")

            if k == 'TESTATA':
                for k_, v_ in v.items():
                    logging.warning(f"k_:{k_}, v_:{v_}")
                    if k_.lower() in filtered_headers:
                        extra_lines_to_print.append(v_)
            elif toks[1:]:
                new_item = {}
                codice = v.get('codice', '')
                if codice.startswith('907'):
                    new_item["pigment_name"] = codice.split('.')[1]
                else:
                    new_item["pigment_name"] = codice

                if v.get('peso') is not None:
                    new_item["weight(g)"] = round(float(v['peso']) / 10., 4)
                else:
                    new_item["weight(g)"] = round(float(v['pesoc']) / 100., 4)
                ingredients.append(new_item)

        properties['extra_lines_to_print'] = extra_lines_to_print
        properties['ingredients'] = ingredients
        properties['meta'] = {'extra_info': extra_info}

        return properties

    @classmethod
    def parse_xml_order(cls, path_to_file):  # pylint: disable=too-many-locals

        properties = {}
        xml_as_dict = None

        # ~ replace_invalid_tags(path_to_file)

        try:
            e = get_encoding(path_to_file)
            with codecs.open(path_to_file, encoding=e) as fd:
                xml_as_dict = xmltodict.parse(fd.read(), encoding=e)
        except Exception:           # pylint: disable=broad-except
            with open(path_to_file) as fd: # pylint: disable=unspecified-encoding
                xml_as_dict = xmltodict.parse(fd.read())

            # ~ logging.warning(json.dumps(xml_as_dict, indent=4))

        if xml_as_dict:
            if xml_as_dict.get("COLORFORMULA", {}).get("FORMULA"):
                properties = cls.parse_nro_xml(xml_as_dict)
                if properties.get('meta'):
                    properties['meta']['header'] = 'nro_xml'
            elif xml_as_dict.get("ColorFormula", {}).get("FormulaRecipe"):
                properties = cls.parse_MIXIT_xml(xml_as_dict)
                if properties.get('meta'):
                    properties['meta']['header'] = 'cti_xml'
            elif xml_as_dict.get("Table", {}).get("Componentes"):
                properties = cls.parse_Besa_SINNEK_xml(xml_as_dict)
                if properties.get('meta'):
                    properties['meta']['header'] = 'Besa_SINNEK_xml'
            else:
                raise Exception(f"unknown xml file:{path_to_file}")

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

        elif cls.codevid_pdf_header in "".join(lines[:4]):
            properties = cls.parse_codevid_txt(lines)

            if properties.get('meta') is not None:
                properties['meta']['header'] = cls.codevid_pdf_header

        return properties

    @classmethod
    def parse_json_order(cls, path_to_file):

        properties = {}

        encoding_ = get_encoding(path_to_file)
        with codecs.open(path_to_file, encoding=encoding_) as fd:
            content = json.load(fd)
            if content.get("header") == "SW CRx formula file":
                properties = cls.parse_sw_json(content)
                properties['meta']['header'] = content['header']
            elif content.get("header") == "AkzoNobel Azure InstrumentCloud":
                properties = cls.parse_akzo_azure_json(content)
                properties['meta']['header'] = content['header']
            else:
                properties = cls.parse_kcc_json(content)
                if properties.get('meta'):
                    properties['meta']['header'] = 'kcc_json'

        return properties

    @classmethod
    def parse_ini_order(cls, path_to_file):

        properties = {}

        config = configparser.ConfigParser()
        config.read(path_to_file)

        if config.has_section("TESTATA"):
            properties = cls.parse_palini_ini_order(config)
            f_name = os.path.split(path_to_file)[1]
            properties['extra_lines_to_print'].append(f_name)

        return properties

    def _do_parse(self, path_to_file, mime_type, file_extension):

        properties_list = [{}]

        try:

            properties = self.parse_ini_order(path_to_file)
            assert properties.get('meta') is not None and not properties['meta'].get('error')
            properties_list = [properties, ]

        except Exception as e:           # pylint: disable=broad-except
            logging.info(traceback.format_exc())
            try:

                properties = self.parse_json_order(path_to_file)
                assert properties.get('meta') is not None and not properties['meta'].get('error')
                properties_list = [properties, ]

            except Exception as e:           # pylint: disable=broad-except

                if mime_type == 'text/xml' or '.xml' in file_extension:
                    properties_list = [self.parse_xml_order(path_to_file), ]
                elif mime_type == 'application/pdf' or '.pdf' in file_extension:
                    properties_list = self.parse_pdf_order(path_to_file)
                    for properties in properties_list:
                        if properties.get('meta'):
                            break
                    else:
                        properties_list = self.parse_pdf_order(path_to_file, fixed_pitch=None)

                elif mime_type == 'text/plain':
                    properties_list = [self.parse_txt_order(path_to_file), ]
                else:
                    raise Exception(f"unknown mime_type:{mime_type} for file:{path_to_file}") from e

        for properties in properties_list:
            if properties.get('meta'):
                properties['meta']['file name'] = os.path.split(path_to_file)[1]

            properties = self._substitute_aliases(properties)

            err_msg = tr_("properties not valid:{}").format(properties)[:400]
            assert properties.get('meta') is not None, err_msg
            assert not properties['meta'].get('error'), err_msg

        return properties_list

    def parse(self, path_to_file):

        mime = magic.Magic(mime=True)
        mime_type = mime.from_file(path_to_file)
        _, file_extension = os.path.splitext(path_to_file)
        logging.warning(f"path_to_file:{path_to_file}, mime_type:{mime_type}, file_extension:{file_extension}")

        properties_list = [{}]

        try:

            properties_list = self._do_parse(path_to_file, mime_type, file_extension)

        except Exception as e:  # pylint: disable=broad-except

            logging.error(f"format error in file:{path_to_file}")
            logging.error(traceback.format_exc())

            msg = tr_("format error in file:{} \n {}").format(path_to_file, e)

            for properties in properties_list:
                properties.setdefault("meta", {})
                properties['meta']['error'] = msg

            if self.exception_handler:
                self.exception_handler(msg)

        return properties_list
