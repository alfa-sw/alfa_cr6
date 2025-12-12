from alfa_CR6_backend.dymo_printer import dymo_print_package_label

package = {
    "name": "850 ml",
    "size": 850,
}

res = dymo_print_package_label(package)
print(res)
