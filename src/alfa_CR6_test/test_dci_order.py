import json
import os
import tempfile
import unittest
from unittest import mock
from types import SimpleNamespace

from alfa_CR6_backend.order_parser import OrderParser
from alfa_CR6_backend.globals import create_printable_image_from_jar, extract_jar_print_data


FORMULA = """[FORMULA1]
NumColorants=2
ColorName=Trial4 RAL 3009 oxidrot
Brand=CCI#433868 RAL3009 Oxidrot
CollectionName=ALFA - CCI# 84054 Trial4 RAL 3009 oxidrot
DispenseUnit=G
Base=CCI-A Gloss Clear
BaseAmount=280
[INGREDIENTS1]
101-A Phathalo Blu=2.3540
40-A Quin Magenta=25.8710
[STATUS]
Cancel=1
[SUMMARY]
TotalFormulas=1
"""


class DciOrderTests(unittest.TestCase):

    def parse_content(self, content):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.dci', delete=False) as fd:
            fd.write(content)
            path = fd.name
        try:
            return OrderParser().parse(path)
        finally:
            os.unlink(path)

    def test_full_pigment_names_and_grams_are_preserved(self):
        orders = self.parse_content(FORMULA)
        self.assertEqual(1, len(orders))
        order = orders[0]
        self.assertNotIn('error', order['meta'])
        self.assertEqual('dci', order['meta']['header'])
        self.assertEqual('280', order['meta']['BaseAmount'])
        self.assertEqual([
            {'pigment_name': '101-A Phathalo Blu', 'weight(g)': 2.354, 'description': ''},
            {'pigment_name': '40-A Quin Magenta', 'weight(g)': 25.871, 'description': ''},
            {'pigment_name': 'CCI-A Gloss Clear', 'weight(g)': 280.0, 'description': ''},
        ], order['ingredients'])
        self.assertEqual([
            'CCI#433868',
            'Trial4',
            'RAL 3009 oxidrot',
            'ALFA - CCI# 84054',
        ], order['extra_lines_to_print'])

    def test_dci_label_prints_all_four_lines(self):
        order = self.parse_content(FORMULA)[0]
        jar = SimpleNamespace(
            barcode='201027001001',
            extra_lines_to_print=order['extra_lines_to_print'],
            unknown_pigments={},
            not_dispensed_ingredients={},
            order=SimpleNamespace(json_properties=json.dumps(order)),
        )
        batch_data = extract_jar_print_data(jar)
        self.assertEqual(4, batch_data['minimum_label_lines'])

        with tempfile.NamedTemporaryFile(suffix='.png') as output:
            for printable in (jar, batch_data):
                with self.subTest(batch=isinstance(printable, dict)):
                    options = {'line_lenght': 24, 'n_of_lines': 3,
                               'rotate': 0, 'print_missing_products': False}
                    with mock.patch('alfa_CR6_backend.globals.EAN13') as barcode:
                        create_printable_image_from_jar(
                            printable, options=options, output_path=output.name)
                    printed_text = barcode.return_value.write.call_args[0][2]
                    self.assertEqual(
                        ['201027001001'] + order['extra_lines_to_print'],
                        printed_text.split('\n'))

    def test_fourth_line_is_not_added_to_other_label_formats(self):
        order = self.parse_content(FORMULA)[0]
        printable = {
            'barcode': '201027001001',
            'extra_lines_to_print': order['extra_lines_to_print'],
            'unknown_pigments': {},
            'not_dispensed_ingredients': {},
            'minimum_label_lines': 0,
        }
        options = {'line_lenght': 24, 'n_of_lines': 3,
                   'rotate': 0, 'print_missing_products': False}
        with tempfile.NamedTemporaryFile(suffix='.png') as output:
            with mock.patch('alfa_CR6_backend.globals.EAN13') as barcode:
                create_printable_image_from_jar(
                    printable, options=options, output_path=output.name)
        printed_text = barcode.return_value.write.call_args[0][2]
        self.assertEqual(
            ['201027001001'] + order['extra_lines_to_print'][:3],
            printed_text.split('\n'))

    def test_dci_does_not_use_ini_order_parser(self):
        with mock.patch.object(OrderParser, 'parse_ini_order', side_effect=AssertionError('INI parser called')):
            orders = self.parse_content(FORMULA)
        self.assertEqual(3, len(orders[0]['ingredients']))
        self.assertNotIn('error', orders[0]['meta'])

    def test_multiple_formulas_produce_separate_orders(self):
        content = FORMULA.replace('TotalFormulas=1', 'TotalFormulas=2')
        content += """[FORMULA2]
NumColorants=1
ColorName=Second color
DispenseUnit=G
Base=CCI-A Gloss Clear
BaseAmount=100
[INGREDIENTS2]
10-A Lamp Black=8.0120
"""
        orders = self.parse_content(content)
        self.assertEqual(2, len(orders))
        self.assertEqual('10-A Lamp Black', orders[1]['ingredients'][0]['pigment_name'])
        self.assertEqual(8.012, orders[1]['ingredients'][0]['weight(g)'])
        self.assertEqual('CCI-A Gloss Clear', orders[1]['ingredients'][1]['pigment_name'])
        self.assertEqual(100.0, orders[1]['ingredients'][1]['weight(g)'])

    def test_rejects_missing_or_empty_base(self):
        for content in (
                FORMULA.replace('Base=CCI-A Gloss Clear\n', ''),
                FORMULA.replace('Base=CCI-A Gloss Clear', 'Base= ')):
            with self.subTest(content=content):
                orders = self.parse_content(content)
                self.assertIn('has no Base', orders[0]['meta']['error'])

    def test_rejects_missing_or_invalid_base_amount(self):
        for content in (
                FORMULA.replace('BaseAmount=280\n', ''),
                FORMULA.replace('BaseAmount=280', 'BaseAmount=0'),
                FORMULA.replace('BaseAmount=280', 'BaseAmount=-1'),
                FORMULA.replace('BaseAmount=280', 'BaseAmount=nan'),
                FORMULA.replace('BaseAmount=280', 'BaseAmount=inf')):
            with self.subTest(content=content):
                orders = self.parse_content(content)
                self.assertIn('no valid BaseAmount', orders[0]['meta']['error'])

    def test_rejects_colorant_count_mismatch_without_fallback(self):
        with mock.patch.object(OrderParser, 'parse_json_order') as json_fallback:
            orders = self.parse_content(FORMULA.replace('NumColorants=2', 'NumColorants=3'))
        json_fallback.assert_not_called()
        self.assertIn('incorrect colorant count', orders[0]['meta']['error'])

    def test_rejects_non_gram_unit(self):
        orders = self.parse_content(FORMULA.replace('DispenseUnit=G', 'DispenseUnit=ML'))
        self.assertIn('unsupported DCI dispense unit', orders[0]['meta']['error'])


if __name__ == '__main__':
    unittest.main()
