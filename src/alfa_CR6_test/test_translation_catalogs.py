"""Check the agreed localization scope without starting Qt or hardware."""

import ast
import collections
import importlib
from pathlib import Path
import string
import unittest


SOURCE_ROOT = Path(__file__).resolve().parents[1]
# Korean is intentionally maintained separately.
LANGUAGES = ("en", "it", "fr", "de", "es", "pl", "da", "fi", "no", "ar", "th", "pt")


class TranslationCatalogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalogs = {code: importlib.import_module("alfa_CR6_backend.lang." + code).D
                        for code in LANGUAGES}

    def test_format_fields_and_specifiers_are_preserved(self):
        formatter = string.Formatter()

        def fields(text):
            return collections.Counter((field, spec, conversion)
                                       for _, field, spec, conversion in formatter.parse(text)
                                       if field is not None)

        for code, catalog in self.catalogs.items():
            for lemma, translation in catalog.items():
                with self.subTest(language=code, lemma=lemma):
                    self.assertEqual(fields(lemma), fields(translation))

    def test_recent_operator_messages_are_localized(self):
        lemmas = (
            "Automatic recovery in progress: heads {}.",
            "Order aborted",
            "Autorecovery code: {}",
            "unknown",
            "Head {} - BARCODE {}\nThe head entered AUTORECOVERY during dispensing.",
            "Unlock unavailable: head status not verified ({}).",
            "No pending files to create orders from.",
            "Create Alfa orders from {} files?\nPrint a label for each order.\nOne can per order.",
            "Created orders from {} files.\nPrinting {} labels.\n"
            "{} files could not be processed and remain in the queue.",
        )
        for code in LANGUAGES:
            for lemma in lemmas:
                with self.subTest(language=code, lemma=lemma):
                    self.assertIn(lemma, self.catalogs[code])
                    if code != "en":
                        self.assertNotEqual(self.catalogs[code][lemma], lemma)

    def test_dispensing_outcomes_keep_the_original_machine_markers(self):
        # do_dispense classifies saved outcomes by looking for the literal
        # "success". Translating these templates can skip a later head.
        lemmas = (
            "success (step:{}) ",
            "failure during dispensation (step:{}) ",
            'failure in sending "DISPENSE_FORMULA" command (step:{}) ',
            "failure waiting for dispensation to start (step:{}) ",
            "failure in waiting for dispensing condition (step:{}) ",
            "cancelled (step:{}) ",
            "cancelled during dispensation (step:{}) ",
        )
        for code, catalog in self.catalogs.items():
            for lemma in lemmas:
                with self.subTest(language=code, lemma=lemma):
                    self.assertEqual(catalog.get(lemma, lemma), lemma)
            self.assertIn("success", catalog.get(lemmas[0], lemmas[0]).format(1))

    def test_excluded_additions_keep_the_original_text(self):
        lemmas = (
            "FIRST COAT", "SECOND COAT", "TEST ALERT MESSAGE: {}",
            " Info ", " Print ", "Nome", "Size", "Barcode infos", "PRINT LABEL",
            "LABEL DATA MISSING", "Print SHUTTLE barcode label",
            "SHUTTLE barcode label information is incomplete",
            "KCC QR decode failed: {}", "pipe with pigment:{} not found.",
        )
        debug_page = SOURCE_ROOT / "alfa_CR6_frontend" / "debug_page.py"
        debug_lemmas = {
            node.args[0].value
            for node in ast.walk(ast.parse(debug_page.read_text(encoding="utf-8")))
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == "tr_" and node.args
            and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)
        }
        for code, catalog in self.catalogs.items():
            for lemma in set(lemmas) | debug_lemmas:
                with self.subTest(language=code, lemma=lemma):
                    self.assertEqual(catalog.get(lemma, lemma), lemma)

    def test_language_names_keep_their_original_spelling(self):
        for code, catalog in self.catalogs.items():
            for name in ("Dutch", "Polish", "English", "Español", "Français", "Deutsch", "Italiano"):
                with self.subTest(language=code, name=name):
                    self.assertEqual(catalog[name], name)

    def test_values_are_formatted_after_translation(self):
        failures = []
        for package in ("alfa_CR6_backend", "alfa_CR6_frontend", "alfa_CR6_flask"):
            for path in (SOURCE_ROOT / package).rglob("*.py"):
                if "lang" in path.parts:
                    continue
                for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                            and node.func.id == "tr_" and node.args):
                        continue
                    argument = node.args[0]
                    formatted = (isinstance(argument, ast.Call)
                                 and isinstance(argument.func, ast.Attribute)
                                 and argument.func.attr == "format")
                    interpolated_sentence = (isinstance(argument, ast.JoinedStr)
                                             and any(isinstance(part, ast.Constant) and part.value.strip()
                                                     for part in argument.values))
                    if formatted or interpolated_sentence:
                        failures.append((str(path.relative_to(SOURCE_ROOT)), node.lineno))
        self.assertEqual(failures, [])


if __name__ == "__main__":
    unittest.main()
