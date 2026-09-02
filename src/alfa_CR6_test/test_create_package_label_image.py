from alfa_CR6_backend.dymo_printer import dymo_print_package_label

package = {
    "name": "Package display name",
    "size": 850,
    "json_info": {
        "label_barcode": {
            "quantity": 850.0,
            "unit": "ML",
            "decimal_separator": ".",
        },
    },
}

res = dymo_print_package_label(package)
print(res)
