# coding: utf-8

"""Formatting and validation for SHUTTLE package barcode labels."""

import json
import math
from decimal import Decimal


SHUTTLE_BARCODE_LABEL_UNITS = ("ML", "L", "LT", "GR", "FL OZ", "OZ")
SHUTTLE_BARCODE_INTEGER_UNITS = frozenset(("FL OZ", "OZ"))
SHUTTLE_BARCODE_DECIMAL_SEPARATORS = (".", ",")


class ShuttleBarcodeLabelError(ValueError):
    """A SHUTTLE label configuration error suitable for the operator UI."""

    def __init__(self, package_name, errors):
        self.package_name = package_name
        self.errors = tuple(errors)

        message = "Cannot print SHUTTLE BARCODE LABEL"
        if package_name:
            message += " for Package {!r}".format(package_name)
        message += ":\n- " + "\n- ".join(self.errors)

        super().__init__(message)


def get_shuttle_barcode_label_config(package):
    """Return only the label_barcode object from Package.json_info."""

    if not isinstance(package, dict):
        raise ShuttleBarcodeLabelError("", ("Package data is invalid.",))

    package_name = package.get("name", "")
    json_info = package.get("json_info")

    if isinstance(json_info, str):
        try:
            json_info = json.loads(json_info or "{}")
        except ValueError as exc:
            raise ShuttleBarcodeLabelError(
                package_name,
                ("Package json_info is not valid JSON.",),
            ) from exc

    if not isinstance(json_info, dict):
        raise ShuttleBarcodeLabelError(
            package_name,
            ("Package json_info must be a JSON object.",),
        )

    label_barcode = json_info.get("label_barcode")
    if label_barcode is None:
        label_barcode = {}
    if not isinstance(label_barcode, dict):
        raise ShuttleBarcodeLabelError(
            package_name,
            ("SHUTTLE BARCODE LABEL configuration must be an object.",),
        )

    return label_barcode


def get_shuttle_barcode_label_info_text(package):
    """Return the three label_barcode fields rendered by the package UI."""

    try:
        label_barcode = get_shuttle_barcode_label_config(package)
    except ShuttleBarcodeLabelError:
        label_barcode = {}

    def display_value(key):
        value = label_barcode.get(key)
        return "N/A" if value in (None, "") else str(value)

    lines = [
        "Quantity: {}".format(display_value("quantity")),
        "Unit: {}".format(display_value("unit")),
    ]
    if label_barcode.get("unit") not in SHUTTLE_BARCODE_INTEGER_UNITS:
        lines.append("Decimal separator: {}".format(
            display_value("decimal_separator")))
    return "\n".join(lines)


def get_shuttle_barcode_label_text(package):
    """Return the Code128 value configured in Package.json_info."""

    label_barcode = get_shuttle_barcode_label_config(package)
    package_name = package.get("name", "")

    errors = []

    unit = label_barcode.get("unit")
    if unit is None:
        unit_error = "Unit of measure is required."
    elif unit not in SHUTTLE_BARCODE_LABEL_UNITS:
        unit_error = (
            "Unit of measure {!r} is not supported. Allowed values: "
            "ML, L, LT, GR, FL OZ, OZ.".format(unit)
        )
    else:
        unit_error = None

    quantity = label_barcode.get("quantity")
    if quantity is None:
        errors.append("Quantity is required.")
    elif isinstance(quantity, bool) or not isinstance(quantity, (int, float)):
        errors.append("Quantity must be a number.")
    elif not math.isfinite(float(quantity)) or quantity <= 0:
        errors.append("Quantity must be greater than zero.")
    elif (unit in SHUTTLE_BARCODE_INTEGER_UNITS
          and not float(quantity).is_integer()):
        errors.append("Quantity must be an integer for {}.".format(unit))

    if unit_error:
        errors.append(unit_error)

    decimal_separator = None
    if unit not in SHUTTLE_BARCODE_INTEGER_UNITS:
        if ("decimal_separator" not in label_barcode
                or label_barcode["decimal_separator"] is None):
            errors.append("Decimal separator is required.")
        else:
            decimal_separator = label_barcode["decimal_separator"]
            if decimal_separator not in SHUTTLE_BARCODE_DECIMAL_SEPARATORS:
                errors.append(
                    "Decimal separator {!r} is not supported. Allowed values: "
                    "point (.) or comma (,).".format(decimal_separator)
                )

    if errors:
        raise ShuttleBarcodeLabelError(package_name, errors)

    quantity_text = format(Decimal(str(quantity)).normalize(), "f")
    if (unit not in SHUTTLE_BARCODE_INTEGER_UNITS
            and decimal_separator == ","):
        quantity_text = quantity_text.replace(".", ",")

    return "{} {}".format(quantity_text, unit)
