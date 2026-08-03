# coding: utf-8

"""Tests for preserving imported DuPont XML order files."""

import os
import tempfile
import unittest

from alfa_CR6_backend.order_file_archive import archive_order_file_if_needed


class DupontOrderArchiveTest(unittest.TestCase):

    def test_dupont_xml_is_copied_to_archive(self):
        with tempfile.TemporaryDirectory() as temp_path:
            source_path = os.path.join(temp_path, 'formula.xml')
            archive_path = os.path.join(temp_path, 'archive')
            with open(source_path, 'w', encoding='UTF-8') as source:
                source.write('<DuPont_Exchange_SpoolFile/>')

            destination = archive_order_file_if_needed(
                source_path,
                [{'meta': {'header': 'dupont_xml'}}],
                data_path=temp_path,
                archive_path=archive_path)

            self.assertTrue(os.path.exists(source_path))
            self.assertEqual(
                destination,
                os.path.join(archive_path, 'formula.xml'))
            with open(destination, encoding='UTF-8') as archived:
                self.assertEqual(
                    archived.read(),
                    '<DuPont_Exchange_SpoolFile/>')

    def test_existing_archive_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temp_path:
            source_path = os.path.join(temp_path, 'formula.xml')
            archive_path = os.path.join(temp_path, 'archive')
            os.makedirs(archive_path)
            with open(source_path, 'w', encoding='UTF-8') as source:
                source.write('new')
            with open(
                    os.path.join(archive_path, 'formula.xml'),
                    'w',
                    encoding='UTF-8') as archived:
                archived.write('old')

            destination = archive_order_file_if_needed(
                source_path,
                [{'meta': {'header': 'dupont_xml'}}],
                data_path=temp_path,
                archive_path=archive_path)

            self.assertEqual(
                destination,
                os.path.join(archive_path, 'formula_1.xml'))
            with open(
                    os.path.join(archive_path, 'formula.xml'),
                    encoding='UTF-8') as archived:
                self.assertEqual(archived.read(), 'old')
            with open(destination, encoding='UTF-8') as archived:
                self.assertEqual(archived.read(), 'new')

    def test_other_order_formats_are_not_archived(self):
        with tempfile.TemporaryDirectory() as temp_path:
            source_path = os.path.join(temp_path, 'formula.xml')
            archive_path = os.path.join(temp_path, 'archive')
            with open(source_path, 'w', encoding='UTF-8') as source:
                source.write('<ColorFormula/>')

            destination = archive_order_file_if_needed(
                source_path,
                [{'meta': {'header': 'cti_xml'}}],
                data_path=temp_path,
                archive_path=archive_path)

            self.assertIsNone(destination)
            self.assertFalse(os.path.exists(archive_path))


if __name__ == '__main__':
    unittest.main()
