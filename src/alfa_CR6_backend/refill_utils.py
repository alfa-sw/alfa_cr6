# coding: utf-8

"""Small shared helpers for refill procedures."""

import math


def get_pipe_index_from_name(pipe_name):
    """Map a B01-B08 or C01-C24 circuit name to its machine index."""
    if (not isinstance(pipe_name, str) or len(pipe_name) != 3
            or not pipe_name[1:].isdigit()):
        raise ValueError("invalid pipe name: {}".format(pipe_name))

    number = int(pipe_name[1:])
    if pipe_name[0] == "B" and 1 <= number <= 8:
        return number - 1
    if pipe_name[0] == "C" and 1 <= number <= 24:
        return number + 7
    raise ValueError("invalid pipe name: {}".format(pipe_name))


def convert_quantity(value, source_unit, target_unit, specific_weight=1,
                     fl_oz_unit=1, fl_oz_fraction=1):
    """Convert CC, GR and FL OZ using the service-page formulas."""
    value = float(value)
    source_unit = str(source_unit or "CC").strip().upper()
    target_unit = str(target_unit or "CC").strip().upper()
    source_unit = "FL OZ" if source_unit.startswith("FL") else source_unit
    target_unit = "FL OZ" if target_unit.startswith("FL") else target_unit

    valid_units = ("CC", "GR", "FL OZ")
    if source_unit not in valid_units or target_unit not in valid_units:
        raise ValueError("unsupported unit conversion: {} to {}".format(
            source_unit, target_unit))

    if "GR" in (source_unit, target_unit):
        specific_weight = float(specific_weight)
        if not math.isfinite(specific_weight) or specific_weight <= 0:
            raise ValueError("invalid specific weight: {}".format(specific_weight))

    if "FL OZ" in (source_unit, target_unit):
        fl_oz_unit = float(fl_oz_unit)
        fl_oz_fraction = float(fl_oz_fraction)
        if (not math.isfinite(fl_oz_unit) or fl_oz_unit <= 0
                or not math.isfinite(fl_oz_fraction) or fl_oz_fraction <= 0):
            raise ValueError("invalid fluid ounce configuration")

    value_cc = value
    if source_unit == "GR":
        value_cc /= specific_weight
    elif source_unit == "FL OZ":
        value_cc *= fl_oz_unit / fl_oz_fraction

    if target_unit == "GR":
        return value_cc * specific_weight
    if target_unit == "FL OZ":
        return value_cc * fl_oz_fraction / fl_oz_unit
    return value_cc
