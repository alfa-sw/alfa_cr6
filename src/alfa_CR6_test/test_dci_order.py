import json
import os
import tempfile
import unittest
from unittest import mock
from types import SimpleNamespace

from barcode import EAN13
from PIL import Image, ImageChops

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

FIXTURES = os.path.join(os.path.dirname(__file__), 'fixtures')
BIG_LABEL_OPTIONS = {
    'dpi': 240, 'module_height': 10, 'module_width': 0.5,
    'font_size': 16, 'text_distance': 5, 'line_lenght': 50,
    'n_of_lines': 3, 'rotate': 0, 'print_missing_products': False,
    'font_path': '/usr/share/fonts/truetype/unfonts-core/UnDotumBold.ttf',
}


class DciOrderTests(unittest.TestCase):

    def parse_fixture(self, name):
        orders = OrderParser().parse(os.path.join(FIXTURES, name))
        self.assertEqual(1, len(orders))
        self.assertNotIn('error', orders[0]['meta'])
        return orders[0]

    @staticmethod
    def jar_for_order(order):
        return SimpleNamespace(
            barcode='261012004001',
            extra_lines_to_print=order['extra_lines_to_print'],
            unknown_pigments={},
            not_dispensed_ingredients={},
            order=SimpleNamespace(json_properties=json.dumps(order)),
        )

    def render_label(self, printable, options):
        # Observe the text but still run the real EAN13/Pillow renderer. This
        # catches clipping that a mocked barcode writer cannot detect.
        original_write = EAN13.write
        with tempfile.NamedTemporaryFile(suffix='.png') as output:
            with mock.patch.object(EAN13, 'write', autospec=True,
                                   side_effect=original_write) as write:
                create_printable_image_from_jar(
                    printable, options=dict(options), output_path=output.name)
            lines = write.call_args[0][3].split('\n')
            with Image.open(output.name) as image:
                rendered = image.copy()
        return lines, rendered

    def assert_text_has_margins(self, image, options):
        if options['rotate']:
            image = image.rotate(-options['rotate'], expand=True)
        # Ignore the barcode itself; every text glyph must stay inside the
        # canvas, including lines which were previously clipped at both edges.
        text_top = int((2 + options['module_height']) * options['dpi'] / 25.4)
        text = image.crop((0, text_top, image.width, image.height)).convert('L')
        bounds = ImageChops.invert(text).getbbox()
        self.assertIsNotNone(bounds)
        margin = max(1, int(round(options['dpi'] / 25.4)))
        self.assertGreaterEqual(bounds[0], margin)
        self.assertLessEqual(bounds[2], image.width - margin)

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
                    with mock.patch.object(EAN13, 'write', autospec=True) as write:
                        create_printable_image_from_jar(
                            printable, options=options, output_path=output.name)
                    printed_text = write.call_args[0][3]
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

    def test_real_charleston_file_removes_matching_collection_suffix(self):
        order = self.parse_fixture('dci_charleston.dci')
        self.assertEqual('CHARLESTON GRAY 243', order['meta']['ColorName'])
        self.assertEqual([
            'Prediction 9 CHARLESTON GRAY 243',
            'CHARLESTON GRAY 243', '', 'ALFA - CCI# 85197',
        ], order['extra_lines_to_print'])
        self.assertEqual(21, len(order['ingredients']))
        self.assertEqual(63.917, order['ingredients'][0]['weight(g)'])
        self.assertEqual(19.579, order['ingredients'][10]['weight(g)'])
        self.assertEqual(15.51952, order['ingredients'][-1]['weight(g)'])

    def test_real_test1_file_keeps_collection_and_zero_ingredients(self):
        order = self.parse_fixture('dci_test1.dci')
        self.assertEqual([
            'Prediction 9 CHARLESTON GRAY 243', 'test 1', '',
            'ALFA - CCI# 85197 CHARLESTON GRAY 243',
        ], order['extra_lines_to_print'])
        self.assertEqual(21, len(order['ingredients']))
        self.assertEqual(13, sum(i['weight(g)'] == 0 for i in order['ingredients']))
        self.assertAlmostEqual(10.985, sum(i['weight(g)'] for i in order['ingredients']))
        self.assertEqual('CCI-A Gloss Clear', order['ingredients'][-1]['pigment_name'])
        self.assertEqual(5, order['ingredients'][-1]['weight(g)'])

    def test_test1_to_test7_keep_collection_when_color_name_is_absent(self):
        with open(os.path.join(FIXTURES, 'dci_test1.dci')) as stream:
            content = stream.read()
        for number in range(1, 8):
            with self.subTest(number=number):
                order = self.parse_content(content.replace('ColorName=test 1',
                                                          f'ColorName=test {number}'))[0]
                self.assertNotIn('error', order['meta'])
                self.assertEqual(f'test {number}', order['extra_lines_to_print'][1])
                self.assertEqual(order['meta']['CollectionName'],
                                 order['extra_lines_to_print'][3])

    def test_long_collection_wraps_without_clipping_in_single_and_batch_labels(self):
        order = self.parse_fixture('dci_test1.dci')
        jar = self.jar_for_order(order)
        for printable in (jar, extract_jar_print_data(jar)):
            for configured_lines in (3, 15):
                with self.subTest(batch=isinstance(printable, dict),
                                  configured_lines=configured_lines):
                    options = dict(BIG_LABEL_OPTIONS, n_of_lines=configured_lines)
                    lines, image = self.render_label(printable, options)
                    self.assertEqual('261012004001', lines[0])
                    self.assertEqual(order['extra_lines_to_print'][:3], lines[1:4])
                    self.assertEqual(2, len([s for s in lines[4:] if s != '.']))
                    self.assertEqual(order['meta']['CollectionName'],
                                     ' '.join(s for s in lines[4:] if s != '.'))
                    self.assert_text_has_margins(image, options)

    def test_long_fields_fit_big_labels_with_different_font_sizes(self):
        order = self.parse_fixture('dci_test1.dci')
        for font_size in (16, 22):
            with self.subTest(font_size=font_size):
                options = dict(BIG_LABEL_OPTIONS, font_size=font_size)
                lines, image = self.render_label(self.jar_for_order(order), options)
                actual = [s for s in lines[1:] if s != '.']
                self.assertIn('', actual)
                self.assertEqual(' '.join(order['extra_lines_to_print']).split(),
                                 ' '.join(actual).split())
                self.assertTrue(all(len(s) <= options['line_lenght'] for s in actual))
                self.assert_text_has_margins(image, options)

    def test_long_unbroken_color_and_brand_are_printed_in_full(self):
        content = FORMULA.replace('ColorName=Trial4 RAL 3009 oxidrot',
                                  'ColorName=' + 'W' * 120)
        content = content.replace('Brand=CCI#433868 RAL3009 Oxidrot',
                                  'Brand=' + 'B' * 100)
        order = self.parse_content(content)[0]
        options = dict(BIG_LABEL_OPTIONS)
        lines, image = self.render_label(self.jar_for_order(order), options)
        actual = ''.join(s for s in lines[1:] if s != '.')
        self.assertEqual(''.join(order['extra_lines_to_print']).replace(' ', ''),
                         actual.replace(' ', ''))
        self.assertTrue(all(len(s) <= options['line_lenght'] for s in lines[1:]))
        self.assert_text_has_margins(image, options)

    def test_missing_product_details_survive_wrapping_and_line_limit(self):
        order = self.parse_fixture('dci_test1.dci')
        jar = self.jar_for_order(order)
        missing = 'Missing pigment with a very long descriptive name'
        not_dispensed = 'Another pigment with a very long descriptive name'
        jar.unknown_pigments = {missing: 2.5}
        jar.not_dispensed_ingredients = {not_dispensed: 3.5}
        options = dict(BIG_LABEL_OPTIONS, print_missing_products=True)
        with mock.patch('alfa_CR6_backend.globals.tr_', side_effect=lambda value: value):
            lines, image = self.render_label(extract_jar_print_data(jar), options)
        text = ' '.join(s for s in lines[1:] if s != '.')
        self.assertIn(missing + ': 2.5', text)
        self.assertIn(not_dispensed + ': 3.5', text)
        self.assertIn('1 product(s) missing:', text)
        self.assertIn('1 product(s) not dispensed:', text)
        self.assert_text_has_margins(image, options)

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
