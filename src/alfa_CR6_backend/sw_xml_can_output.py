# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name
# pylint: disable=too-many-lines
# pylint: disable=logging-fstring-interpolation, consider-using-f-string

import sys
import json
import logging
import xmltodict
import sqlalchemy

from alfa_CR6_backend.models import compile_barcode


class SwXmlCanOutput:

    template_struct_json = """{
        "weighing": {
            "date": "2023-05-04-T13:53:28Z",
            "status": "3",
            "jobID": "539471",
            "operatorID": "david",
            "colordata": {
                "colorid": "78",
                "brand": {
                    "code": "CUSTOM",
                    "name": "CUSTOM"
                },
                "region": null,
                "code": "MINI",
                "variant": null,
                "name": "NARAJA",
                "remark": null,
                "mutationdate": "2023-05-04-T13:24:11"
            },
            "formula": {
                "quality": {
                    "id": "7",
                    "name": "900+"
                },
                "type": {
                    "id": "0",
                    "name": null
                },
                "undercoat": {
                    "brandcode": "UC",
                    "colorcode": "GS905"
                },
                "pictograms": {
                    "@count": "1",
                    "picto": {
                        "@number": "1",
                        "id": "184",
                        "description": {
                            "@language": "es-ES",
                            "#text": "Undercoat / sistema de 3 capas."
                        }
                    }
                },
                "mutationdate": "2023-05-04-T13:24:11",
                "weights": {
                    "@unit": "gr",
                    "calculated": "281.465",
                    "recalculated": "281.465",
                    "poured": "283"
                },
                "volumes": {
                    "@unit": "l",
                    "calculated": "0.275",
                    "recalculated": "0.275",
                    "poured": "0.276559"
                },
                "vocregulatory": {
                    "@unit": "gr/l",
                    "#text": "305.687"
                },
                "cost": "0",
                "lines": {
                    "@count": "6",
                    "line": [
                        {
                            "@number": "1",
                            "code": "940",
                            "name": "MM 940 WaterBase",
                            "weights": {
                                "@unit": "gr",
                                "calculated": "105.783",
                                "recalculated": "105.783",
                                "poured": "105.8"
                            },
                            "density": "1.016",
                            "volumes": {
                                "@unit": "l",
                                "calculated": "0.104117",
                                "recalculated": "0.104117",
                                "poured": "0.104134"
                            },
                            "cost": "0"
                        },
                        {
                            "@number": "2",
                            "code": "947",
                            "name": "MM 947 Waterbase",
                            "weights": {
                                "@unit": "gr",
                                "calculated": "101.078",
                                "recalculated": "101.078",
                                "poured": "101.1"
                            },
                            "density": "1.011",
                            "volumes": {
                                "@unit": "l",
                                "calculated": "0.0999785",
                                "recalculated": "0.0999785",
                                "poured": "0.1"
                            },
                            "cost": "0"
                        },
                        {
                            "@number": "3",
                            "code": "900",
                            "name": "MM 900 WaterBase",
                            "weights": {
                                "@unit": "gr",
                                "calculated": "42.93",
                                "recalculated": "42.93",
                                "poured": "43"
                            },
                            "density": "1.107",
                            "volumes": {
                                "@unit": "l",
                                "calculated": "0.0387805",
                                "recalculated": "0.0387805",
                                "poured": "0.0388437"
                            },
                            "cost": "0"
                        },
                        {
                            "@number": "4",
                            "code": "938",
                            "name": "MM 938 WaterBase",
                            "weights": {
                                "@unit": "gr",
                                "calculated": "5.26985",
                                "recalculated": "5.26985",
                                "poured": "5.3"
                            },
                            "density": "1.0243",
                            "volumes": {
                                "@unit": "l",
                                "calculated": "0.00514483",
                                "recalculated": "0.00514483",
                                "poured": "0.00517427"
                            },
                            "cost": "0"
                        },
                        {
                            "@number": "5",
                            "code": "979",
                            "name": "MM 979 WaterBase",
                            "weights": {
                                "@unit": "gr",
                                "calculated": "1.97941",
                                "recalculated": "1.97941",
                                "poured": "2"
                            },
                            "density": "1",
                            "volumes": {
                                "@unit": "l",
                                "calculated": "0.00197941",
                                "recalculated": "0.00197941",
                                "poured": "0.002"
                            },
                            "cost": "0"
                        },
                        {
                            "@number": "6",
                            "code": "9-151",
                            "name": "9-151     WaterBase Thinner",
                            "weights": {
                                "@unit": "gr",
                                "calculated": "24.425",
                                "recalculated": "24.425",
                                "poured": "25.8"
                            },
                            "density": "0.977",
                            "volumes": {
                                "@unit": "l",
                                "calculated": "0.025",
                                "recalculated": "0.025",
                                "poured": "0.0264074"
                            },
                            "cost": "0"
                        }
                    ]
                }
            }
        }
    }"""

    template_struct = json.loads(template_struct_json)
    template_struct_ = {
        'weighing': {
            'date': '2023-05-04-T13:53:28Z',
            'status': '3',
            'jobID': '539471',
            'operatorID': 'david',
            'colordata': {
                'colorid': '78',
                'brand': {'code': 'CUSTOM', 'name': 'CUSTOM'},
                'region': None,
                'code': 'MINI',
                'variant': None,
                'name': 'NARAJA',
                'remark': None,
                'mutationdate': '2023-05-04-T13:24:11'
            },
            'formula': {
                'quality': {'id': '7', 'name': '900+'},
                'type': {'id': '0', 'name': None},
                'undercoat': {'brandcode': 'UC', 'colorcode': 'GS905'},
                'pictograms': {
                    '@count': '1',
                    'picto': {'@number': '1', 'id': '184', 'description': {'@language': 'es-ES', '#text': 'Undercoat / sistema de 3 capas.'}}
                },
                'mutationdate': '2023-05-04-T13:24:11',
                'weights': {
                    '@unit': 'gr', 'calculated': '281.465', 'recalculated': '281.465', 'poured': '283'
                },
                # ~ 'volumes': {
                # ~ '@unit': 'l', 'calculated': '0', 'recalculated': '0', 'poured': '0'
                # ~ },
                # ~ 'vocregulatory': {
                # ~ '@unit': 'gr/l', '#text': '305.687'
                # ~ },
                'cost': '0',
                'lines': {
                    '@count': '6',
                    'line': [
                        {
                            '@number': '1',
                            'code': '940',
                            'name': 'MM 940 WaterBase',
                            'weights': {'@unit': 'gr', 'calculated': '105.783', 'recalculated': '105.783', 'poured': '105.8'},
                            'density': '1.016',
                            'volumes': {'@unit': 'l', 'calculated': '0.104117', 'recalculated': '0.104117', 'poured': '0.104134'},
                            'cost': '0'
                        }, {
                            '@number': '2',
                            'code': '947',
                            'name': 'MM 947 Waterbase',
                            'weights': {'@unit': 'gr', 'calculated': '101.078', 'recalculated': '101.078', 'poured': '101.1'},
                            'density': '1.011',
                            'volumes': {'@unit': 'l', 'calculated': '0.0999785', 'recalculated': '0.0999785', 'poured': '0.1'},
                            'cost': '0'
                        }, {
                            '@number': '3',
                            'code': '900',
                            'name': 'MM 900 WaterBase',
                            'weights': {'@unit': 'gr', 'calculated': '42.93', 'recalculated': '42.93', 'poured': '43'},
                            'density': '1.107',
                            'volumes': {'@unit': 'l', 'calculated': '0.0387805', 'recalculated': '0.0387805', 'poured': '0.0388437'},
                            'cost': '0'
                        }, {
                            '@number': '4',
                            'code': '938',
                            'name': 'MM 938 WaterBase',
                            'weights': {'@unit': 'gr', 'calculated': '5.26985', 'recalculated': '5.26985', 'poured': '5.3'},
                            'density': '1.0243',
                            'volumes': {'@unit': 'l', 'calculated': '0.00514483', 'recalculated': '0.00514483', 'poured': '0.00517427'},
                            'cost': '0'
                        }, {
                            '@number': '5',
                            'code': '979',
                            'name': 'MM 979 WaterBase',
                            'weights': {'@unit': 'gr', 'calculated': '1.97941', 'recalculated': '1.97941', 'poured': '2'},
                            'density': '1',
                            'volumes': {'@unit': 'l', 'calculated': '0.00197941', 'recalculated': '0.00197941', 'poured': '0.002'},
                            'cost': '0'
                        }, {
                            '@number': '6',
                            'code': '9-151',
                            'name': '9-151     WaterBase Thinner',
                            'weights': {'@unit': 'gr', 'calculated': '24.425', 'recalculated': '24.425', 'poured': '25.8'},
                            'density': '0.977',
                            'volumes': {'@unit': 'l', 'calculated': '0.025', 'recalculated': '0.025', 'poured': '0.0264074'},
                            'cost': '0'
                        }
                    ]
                }
            }
        }
    }

    def __init__(self, jar, order):

        self.jar = jar
        self.order = order

        self.out_struct = None

    def parse(self):

        weighing = self.template_struct_['weighing'].copy()

        # ~ logging.info(f"jar:{self.jar}")
        # ~ logging.info(f"\nid:{self.order.id},\n o_properties:{self.order.json_properties}")
        # ~ logging.info(f"\nid:{self.jar.id},\n j_properties:{self.jar.json_properties}")
        j_properties = json.loads(self.jar.json_properties)
        o_properties = json.loads(self.order.json_properties)

        o_total_weight_gr = sum([i.get("weight(g)") for i in j_properties.get("order_ingredients", [])])
        j_total_weight_gr = sum(list(j_properties.get('dispensed_quantities_gr', {}).values()))
        o_total_vol_lt = 0
        j_total_vol_lt = 0

        weighing['date'] = self.jar.date_modified
        weighing['status'] = '0'
        weighing['jobID'] = o_properties.get('jobId', '')
        weighing['operatorID'] = o_properties.get('operatorID', '')

        weighing['colordata']['colorid'] = o_properties.get('formulaNumber', '')
        weighing['colordata']['mutationdate'] = o_properties.get('meta', {}).get('dateModified', '')
        weighing['colordata']['code'] = o_properties.get('meta', {}).get('colorCode', '')
        weighing['colordata']['variant'] = o_properties.get('meta', {}).get('variantCode', '')
        weighing['colordata']['name'] = o_properties.get('meta', {}).get('colorName', '')
        weighing['colordata']['brand'] = o_properties.get('meta', {}).get('brand', '')
        weighing['colordata']['region'] = o_properties.get('meta', {}).get('region', '')
        weighing['colordata']['remark'] = o_properties.get('meta', {}).get('remark', '')

        weighing['formula']['mutationdate'] = o_properties.get('meta', {}).get('dateModified', '')
        weighing['formula']['quality'] = o_properties.get('meta', {}).get('quality', '')
        weighing['formula']['type'] = o_properties.get('meta', {}).get('remark', '')
        weighing['formula']['undercoat'] = o_properties.get('meta', {}).get('undercoat', '')
        weighing['formula']['pictograms'] = o_properties.get('meta', {}).get('pictograms', '')
        weighing['formula']['weights'] = {
            '@unit': 'gr',
            'calculated': round(o_total_weight_gr, 3),
            'recalculated': round(o_total_weight_gr, 3),
            'poured': round(j_total_weight_gr, 3)
        }
        # ~ weighing['formula']['volumes'] = {
        # ~ '@unit': 'l',
        # ~ 'calculated': round(o_total_vol_lt, 6),
        # ~ 'recalculated': round(o_total_vol_lt, 6),
        # ~ 'poured': round(j_total_vol_lt, 6)
        # ~ }

        weighing['formula']['lines'] = {
            '@count': len(j_properties.get("order_ingredients", [])),
            'line': []
        }

        for i, o in enumerate(j_properties.get("dispensed_quantities_gr", {}).items()):
            k, v = o

            density = 1
            for item in j_properties.get("specific_weights", {}).values():
                for code_, sw in item.items():
                    if k == code_:
                        density = sw
                        break

            vol_l = 0.001 * density * v
            i = {
                '@number': i + 1,
                'code': k,
                # TODO: get the 'description' of the pigment to be used as 'name' 
                # ~ 'name': 'MM 940 WaterBase',
                'weights': {'@unit': 'gr', 'calculated': round(v, 3), 'recalculated': round(v, 3), 'poured': round(v, 3)},
                'density': round(density, 3),
                'volumes': {'@unit': 'l', 'calculated': round(vol_l, 6), 'recalculated': round(vol_l, 6), 'poured': round(vol_l, 6)},
                'cost': '0'
            }
            weighing['formula']['lines']['line'].append(i)

        self.out_struct = {'weighing': weighing}

        # ~ logging.info(f"\nid:{self.jar.id},\n j_properties:{j_properties}")
        # ~ logging.info(f"\nid:{self.order.id},\n o_properties:{o_properties}")
        # ~ logging.info(f"{self.template_struct}")

    def to_xml(self):

        xml_ = xmltodict.unparse(self.out_struct, encoding='UTF-16', pretty=True)

        return xml_


def main():

    logging.basicConfig(
        stream=sys.stdout, level='INFO',
        format="[%(asctime)s]%(levelname)s %(funcName)s() %(filename)s:%(lineno)d %(message)s")

    engine = sqlalchemy.create_engine("sqlite:////opt/alfa_cr6/data/CRx_v0_SW.sqlite")

    conn = engine.connect()
    metadata = sqlalchemy.MetaData()  # extracting the metadata
    jar_table = sqlalchemy.Table('jar', metadata, autoload=True, autoload_with=engine)  # Table object
    order_table = sqlalchemy.Table('order', metadata, autoload=True, autoload_with=engine)  # Table object
    logging.info(f"jar_table.columns.keys:{jar_table.columns.keys()}")

    # ~ query = jar_table.select().where(jar_table.columns.Major.in_(['English','Math']))
    q = jar_table.select().where(jar_table.columns.status.in_(['DONE'])).limit(10)

    # ~ query = sqlalchemy.select([jar_table, order_table]).select_from(jar_table.join(order_table, jar_table.columns.order_id == order_table.columns.id)).limit(1)
    # ~ query = sqlalchemy.select([jar_table, order_table])

    # ~ [division.columns.division,match.columns.Div]

    for j in conn.execute(q).fetchall():
        q_ = order_table.select().where(order_table.columns.id == j.order_id)
        o = conn.execute(q_).first()
        c = SwXmlCanOutput(j, o)
        c.parse()
        c.to_xml()
        out_file_name = '/opt/alfa_cr6/tmp/' + str(compile_barcode(o.order_nr, j.index)) + ".xml"
        with open(out_file_name, 'w', encoding='UTF-16') as fd:
            fd.write(c.to_xml())


if __name__ == "__main__":
    main()
