# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=invalid-name

import os
import sys
import random
import json
import logging
import http.client

import requests

LOG_LEVEL = 'INFO'


""" to be reported on label:

"brand",
"quality",
"colorCode",
"quantity",
"batchId",

"""


URL_PREFIX = '/api/v1'

SAMLPE_FILTER = [{"name": "description", "op": "==", "val": "1376848525"}]


def test_restless(resource_name, host):

    port = 8090
    method = 'GET'
    # ~ url = f'{URL_PREFIX}/{resource_name}?page[size]=5&page[number]=2'
    # ~ url = f'{URL_PREFIX}/{resource_name}'
    url = f'{URL_PREFIX}/{resource_name}'

    hdrs = {'Content-type': 'application/json'}

    conn = http.client.HTTPConnection(host=host, port=port, timeout=5)

    # ~ url = url + "?include=jars&filter[objects]=" + "".join(json.dumps(SAMLPE_FILTER).split())

    logging.warning(url)

    conn.request(method=method, url=url, headers=hdrs)
    response = conn.getresponse()

    resp_str = response.read().decode()
    logging.warning(resp_str)
    resp_dict = json.loads(resp_str)

    resp = json.dumps(resp_dict, indent=2, ensure_ascii=False)

    logging.warning(resp)


def ask_orders_by_job_id(job_id, host):

    port = 8090
    method = 'GET'
    url = f'{URL_PREFIX}/orders_by_job_id/{job_id}'

    hdrs = {'Content-type': 'application/json'}

    conn = http.client.HTTPConnection(host=host, port=port, timeout=5)
    # ~ logging.warning(f"conn:{conn}, host:port={host}:{port}")
    conn.request(method=method, url=url, headers=hdrs)
    response = conn.getresponse()

    resp_str = response.read().decode()
    resp_dict = json.loads(resp_str)
    # ~ for d in resp_dict['data']:
    # ~ d["json_properties"] = json.loads(d["json_properties"])
    resp = json.dumps(resp_dict, indent=2, ensure_ascii=False)
    logging.warning(resp)


def upload_formula_file(file_path, host):

    port = 8090
    url = f"http://{HOST}:{port}/upload_formula_file"
    logging.warning(f"url:{url}")

    with open(file_path, 'rb') as fd:
        files = {'file': (os.path.basename(file_path), fd, 'application/json')}
        r = requests.post(url, files=files)

        logging.warning(f"r:{r}")
        # ~ logging.warning(r.prepare().body.decode('ascii'))


def upload_json_formula(host):

    SAMPLE_FORMULAS = [
        {
            "header": "SW CRx formula file",
            "version": "16.0.3.1",
            "system": "Octoral Information Services",
            "operatorId": "",
            "jobId": "",
            "batchId": random.randint(0, 2000000000),
            "action": None,
            "meta": {
                "brand": "UC",
                "region": "",
                "colorCode": f"alfaTest-{random.randint(1, 10)}",
                "variantCode": "",
                "colorName": "GREY SHADE: WHITE",
                "secondName": "",
                "year": "/",
                "remark": "",
                "quality": "DeBeer900",
                "undercoat": "",
                "pictograms": "180,180,180,180,180",
                "dateModified": "16/06/2021",
                "quantity(l)": 0.5,
                "cumulative": 0.0,
                "extraInfo": [
                    "UC_GS903__GREY SHADE: WHITE",
                    ""
                ]
            },
            "ingredients": [
                {
                    "code": "W10",
                    "weight(g)": 116.6687740407977,
                    "tolerance": 0,
                    "description": None
                },
                {
                    "code": "W11",
                    "weight(g)": 116.6687740407977,
                    "tolerance": 0,
                    "description": None
                },
                # ~ {
                # ~ "code": "W12",
                # ~ "weight(g)": 116.6687740407977,
                # ~ "tolerance": 0,
                # ~ "description": None
                # ~ },
                {
                    "code": "W98",
                    "weight(g)": 0.4907623708028845,
                    "tolerance": 0,
                    "description": None
                },
                {
                    "code": "W88",
                    "weight(g)": 0.24772933071628858,
                    "tolerance": 0,
                    "description": None
                },
                {
                    "code": "BW88",
                    "weight(g)": 0.24772933071628858,
                    "tolerance": 0,
                    "description": None
                },
                {
                    "code": "BW89",
                    "weight(g)": 0.24772933071628858,
                    "tolerance": 0,
                    "description": None
                },
                {
                    "code": "BW90",
                    "weight(g)": 0.24772933071628858,
                    "tolerance": 0,
                    "description": None
                },
                {
                    "code": "BW91",
                    "weight(g)": 0.24772933071628858,
                    "tolerance": 0,
                    "description": None
                },
                {
                    "code": "BW92",
                    "weight(g)": 0.24772933071628858,
                    "tolerance": 0,
                    "description": None
                },
                {
                    "code": "BW93",
                    "weight(g)": 0.24772933071628858,
                    "tolerance": 0,
                    "description": None
                },
                {
                    "code": "BW94",
                    "weight(g)": 0.24772933071628858,
                    "tolerance": 0,
                    "description": None
                },
                {
                    "code": "TW80",
                    "weight(g)": 9.770000145584346,
                    "tolerance": 0,
                    "description": None
                }
            ]
        },
        {
            "header": "SW CRx formula file",
            "version": "1.0.0",
            "system": "OCTORAL",
            "operatorId": "",
            "jobId": "",
            "batchId": random.randint(0, 2000000000),
            "action": None,
            "meta": {
                "brand": "FORD",
                "region": "",
                "colorCode": "724x",
                "variantCode": "",
                "colorName": " MIDNIGHT SKY PEARL",
                "secondName": "GRIS METEORE PEARL",
                "year": "2011/",
                "remark": "",
                "quality": "Octobase Eco Plus",
                "undercoat": "",
                "pictograms": "",
                "dateModified": "",
                "quantity(l)": 0.1,
                "cumulative": 0.0,
                "extraInfo": [
                    ""
                ]
            },
            "ingredients": [
                {
                    "code": "W89",
                    "weight(g)": 1.0,
                    "tolerance": 0,
                    "description": ""
                },
                {
                    "code": "W23",
                    "weight(g)": 2.0001,
                    "tolerance": 0,
                    "description": ""
                },
                {
                    "code": "W97",
                    "weight(g)": 3.0,
                    "tolerance": 0,
                    "description": ""
                },
                {
                    "code": "W00",
                    "weight(g)": 4.0001,
                    "tolerance": 0,
                    "description": ""
                }
            ]
        }
    ]

    port = 8090
    method = 'POST'
    url = '/upload_json_formula'
    for sample_formula in SAMPLE_FORMULAS:
        json_data_as_string = json.dumps(sample_formula)

        hdrs = {'Content-type': 'application/json'}

        conn = http.client.HTTPConnection(host=host, port=port, timeout=5)
        # ~ logging.warning(f"conn:{conn}, host:port={host}:{port}")
        conn.request(method=method, url=url, body=json_data_as_string, headers=hdrs)
        response = conn.getresponse()

        _resp = response.read().decode()
        _resp = json.loads(_resp)

        # ~ logging.warning(f"_resp:{json.dump(json.loads(_resp), indent=2)}")
        logging.warning(f"_resp:{json.dumps(_resp, indent=2)}")


def main():

    logging.basicConfig(
        stream=sys.stdout, level=LOG_LEVEL,
        format="[%(asctime)s]%(levelname)s %(funcName)s() %(filename)s:%(lineno)d %(message)s")

    host = sys.argv[1:] and sys.argv[1] or '127.0.0.1'
    opt = sys.argv[2:] and sys.argv[2] or '-u' 
    arg = sys.argv[3:] and sys.argv[3] or ''
    n_of_repeat = sys.argv[4:] and int(sys.argv[4]) or 1
    more = sys.argv[5:] and sys.argv[5] or ''

    if opt == '-u':
        # ~ upload_json_formula(host, arg, n_of_repeat, more)
        upload_json_formula(host)
    elif opt == '-r':
        test_restless(arg, host)
    elif opt == '-j':
        ask_orders_by_job_id(arg, host)
    elif opt == '-f':
        upload_formula_file(arg, host)
    else:
        raise Exception('unknown option')


main()
