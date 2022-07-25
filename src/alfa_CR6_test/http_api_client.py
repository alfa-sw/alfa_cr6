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

HOST = '127.0.0.1'
# ~ HOST = '93.147.171.2'
# ~ HOST = '192.168.0.100'
# ~ HOST = '192.168.12.122'


""" to be reported on label:

"brand",
"quality",
"colorCode",
"quantity",
"batchId",

"""


URL_PREFIX = '/api/v1'

SAMLPE_FILTER = [{"name":"description","op":"==","val":"1376848525"}]


def test_restless(resource_name):

    host = HOST
    port = 8090
    method = 'GET'
    # ~ url = f'{URL_PREFIX}/{resource_name}?page[size]=5&page[number]=2'
    # ~ url = f'{URL_PREFIX}/{resource_name}'
    url = f'{URL_PREFIX}/{resource_name}'

    hdrs = {'Content-type': 'application/json'}

    conn = http.client.HTTPConnection(host=host, port=port, timeout=5)

    url = url + "?include=jars&filter[objects]=" + "".join(json.dumps(SAMLPE_FILTER).split())

    print(url)

    conn.request(method=method, url=url, headers=hdrs)
    response = conn.getresponse()

    resp_str = response.read().decode()
    resp_dict = json.loads(resp_str)

    resp = json.dumps(resp_dict, indent=2, ensure_ascii=False)

    print(resp)


def ask_orders_by_job_id(job_id):

    host = HOST
    port = 8090
    method = 'GET'
    url = f'{URL_PREFIX}/orders_by_job_id/{job_id}'

    hdrs = {'Content-type': 'application/json'}

    conn = http.client.HTTPConnection(host=host, port=port, timeout=5)
    # ~ print(f"conn:{conn}, host:port={host}:{port}")
    conn.request(method=method, url=url, headers=hdrs)
    response = conn.getresponse()

    resp_str = response.read().decode()
    resp_dict = json.loads(resp_str)
    # ~ for d in resp_dict['data']:
        # ~ d["json_properties"] = json.loads(d["json_properties"])
    resp = json.dumps(resp_dict, indent=2, ensure_ascii=False)
    print(resp)


def upload_formula_file(file_path):

    port = 8090
    url = f"http://{HOST}:{port}/upload_formula_file"
    print(f"url:{url}")

    with open(file_path,'rb') as fd:
        files = {'file': (os.path.basename(file_path), fd, 'application/json')}
        r = requests.post(url, files=files)

        print(f"r:{r}")
        # ~ print(r.prepare().body.decode('ascii'))

def upload_json_formula():

    SAMPLE_FORMULA = {
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
        "quantity": 500.0,
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
    }

    host = HOST
    port = 8090
    method = 'POST'
    url = '/upload_json_formula'
    json_data_as_string = json.dumps(SAMPLE_FORMULA)

    hdrs = {'Content-type': 'application/json'}

    conn = http.client.HTTPConnection(host=host, port=port, timeout=5)
    # ~ print(f"conn:{conn}, host:port={host}:{port}")
    conn.request(method=method, url=url, body=json_data_as_string, headers=hdrs)
    response = conn.getresponse()

    print(response.read().decode())


def main():

    opt = sys.argv[1:] and sys.argv[1]
    arg = sys.argv[2:] and sys.argv[2]

    if opt == []:
        upload_json_formula()
    elif opt == '-r':
        test_restless(arg)
    elif opt == '-j':
        ask_orders_by_job_id(arg)
    elif opt == '-f':
        upload_formula_file(arg)
    else:
        raise Exception('unknown option')


main()
