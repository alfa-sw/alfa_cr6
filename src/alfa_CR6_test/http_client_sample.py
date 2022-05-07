# coding: utf-8

# pylint: disable=missing-docstring

import http.client
import json


SAMPLE_FORMULA = {
    "header": "SW CRx formula file",
    "version": "0.0.1",
    "system": "COINS",
    "jobId": "XFER_TEST",
    "meta": {
        "Brand": "UC     UNDERCOAT",
        "Region": "",
        "Colour code": "GS905",
        "Variant": "",
        "Colour name": "GREY SHADE: LIGHT GREY",
        "Second-name": "",
        "Year": "/",
        "Remark": "HSS 2",
        "Quality": "Octobase Eco Plus",
        "Undercoat": "",
        "Pictograms": "",
        "Mutation date": "16-06-2021",
        "Quantity": "1,10 Litro",
        "Cumulative": "No",
        "extra_info": [
            "Octoral Information Services - COINS",
            "Data 19-10-2021 [11:56]",
            "Overview: Formula",
            "COV [gr/l]: 275,2",
            "We strongly advise you to check the colour before use, ",
            "for many reasons the car colour can be slightly different than the mixed colour."
        ]
    },
    "ingredients": [
        {"code": "W46",
            "weight(g)": 69.9,
            "description": "TN11-W0PR-J00M-1YWC"},
        {"code": "W47",
            "weight(g)": 44.4,
            "description": "G721-F0HH-Q003-PCYT"},
        {"code": "W48",
            "weight(g)": 26.4,
            "description": "1T11-X02J-500M-CP2G"},
        {"code": "W50",
            "weight(g)": 20.0,
            "description": "QG21-Y0KQ-M00K-NDR0"},
        {"code": "W909",
            "weight(g)": 5.6,
            "description": "W909"},
        {"code": "W60",
            "weight(g)": 0.9,
            "description": "-"},
        {"code": "TW80",
            "weight(g)": 19.5,
            "description": "-"}
    ]
}


def main():

    host = '127.0.0.1'
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
