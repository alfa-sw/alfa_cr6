# coding: utf-8

# pylint: disable=missing-docstring

import http.client
import json

""" to be reported on label:

"brand",
"quality",
"colorCode",
"quantity",
"batchId",
 
"""

SAMPLE_FORMULA = {
  "header": "SW CRx formula file",
  "version": "16.0.3.1",
  "system": "Octoral Information Services",
  "operatorId": "",
  "jobId": "",
  "batchId": 1857629189,
  "action": None,
  "meta": {
    "brand": "UC",
    "region": "",
    "colorCode": "GIOVANNI_TEST",
    "variantCode": "",
    "colorName": "GREY SHADE: WHITE",
    "secondName": "",
    "year": "/",
    "remark": "",
    "quality": "DeBeer900",
    "undercoat": "",
    "pictograms": "180,180,180,180,180",
    "dateModified": "16/06/2021",
    "quantity": 0.0,
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
      "code": "TW80",
      "weight(g)": 9.770000145584346,
      "tolerance": 0,
      "description": None
    }
  ]
}

def main():

    host = '127.0.0.1'
    host = '192.168.12.122'
    port = 8090
    method='POST'
    url='/upload_json_formula'
    json_data_as_string = json.dumps(SAMPLE_FORMULA)

    hdrs = {'Content-type': 'application/json'}

    conn = http.client.HTTPConnection(host=host, port=port, timeout=5)
    print(f"conn:{conn}, host:port={host}:{port}")
    conn.request(method=method, url=url, body=json_data_as_string, headers=hdrs)
    response = conn.getresponse()

    print(response.read().decode())

main()
