# coding: utf-8

"""Impedisce il drift della lista esplicita dei test hardware-free."""

import collections
import os
import unittest

from alfa_CR6_test.hardware_free_suite import (
    CORE_TEST_MODULES,
    EXCLUDED_TEST_MODULES,
    NETWORK_TEST_MODULES,
)


class HardwareFreeSuiteManifestTest(unittest.TestCase):

    @staticmethod
    def _discover_test_modules():
        package_path = os.path.dirname(os.path.abspath(__file__))
        modules = set()
        for directory, _subdirectories, filenames in os.walk(package_path):
            for filename in filenames:
                if not filename.startswith("test_") or not filename.endswith(".py"):
                    continue
                relative_path = os.path.relpath(
                    os.path.join(directory, filename), package_path
                )
                relative_module = os.path.splitext(relative_path)[0]
                modules.add(
                    "alfa_CR6_test.{}".format(
                        relative_module.replace(os.path.sep, ".")
                    )
                )
        return modules

    def test_every_test_module_has_exactly_one_classification(self):
        discovered = self._discover_test_modules()
        classified_list = (
            list(CORE_TEST_MODULES)
            + list(NETWORK_TEST_MODULES)
            + list(EXCLUDED_TEST_MODULES)
        )
        classified = set(classified_list)
        occurrences = collections.Counter(classified_list)
        duplicates = sorted(
            module for module, count in occurrences.items() if count != 1
        )
        unclassified = sorted(discovered - classified)
        stale = sorted(classified - discovered)
        missing_reasons = sorted(
            module for module, reason in EXCLUDED_TEST_MODULES.items()
            if not reason.strip()
        )

        self.assertEqual(duplicates, [], "moduli classificati piu' volte")
        self.assertEqual(
            unclassified, [],
            "nuovi test non classificati come core, network o esclusi",
        )
        self.assertEqual(stale, [], "moduli classificati ma non presenti")
        self.assertEqual(
            missing_reasons, [], "moduli esclusi senza motivazione"
        )


if __name__ == "__main__":
    unittest.main()
