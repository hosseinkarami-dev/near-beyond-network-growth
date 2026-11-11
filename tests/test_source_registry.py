"""Contract checks for canonical raw source configuration."""

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from common import RAW_DATA_DIR, SOURCES, SOURCES_BY_NAME, SourceProvider, SourceName, raw_path


class SourceRegistryTests(unittest.TestCase):
    def test_source_names_are_unique_and_all_sources_have_typed_providers(self):
        self.assertEqual(len(SOURCES_BY_NAME), len(SOURCES))
        self.assertEqual(len({source.name for source in SOURCES}), len(SOURCES))
        self.assertTrue(all(isinstance(source.name, SourceName) for source in SOURCES))
        self.assertTrue(all(isinstance(source.provider, SourceProvider) for source in SOURCES))

    def test_raw_paths_are_explicit_and_stay_under_the_raw_root(self):
        for source in SOURCES:
            with self.subTest(source=source.name):
                path = raw_path(source)
                self.assertTrue(path.is_relative_to(RAW_DATA_DIR))
                self.assertTrue(source.raw_filename.endswith(".json"))


if __name__ == "__main__":
    unittest.main()
