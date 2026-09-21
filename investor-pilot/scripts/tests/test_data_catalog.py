import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("data_catalog", Path(__file__).parents[1] / "data_catalog.py")
catalog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(catalog)

class CatalogTests(unittest.TestCase):
    def test_path_is_not_geographic_proof(self):
        status, _ = catalog.geography({}, "", "Niger delta Fields/log.las")
        self.assertEqual(status, "niger_delta_path_hint_only")
    def test_nigeria_is_not_automatically_niger_delta(self):
        self.assertEqual(catalog.geography({"CTRY": {"value": "NG"}}, "", "")[0], "nigeria_basin_unverified")
    def test_conflicting_country_is_blocked(self):
        self.assertEqual(catalog.geography({"CTRY": {"value": "NORWAY"}}, "NIGER_DELTA", "")[0], "conflicting_metadata")
    def test_ambiguous_country_codes_are_not_foreign(self):
        for code in ["NIG", "NI", "XX"]:
            self.assertEqual(catalog.geography({"CTRY": {"value": code}}, "", "")[0], "ambiguous_country_code")
    def test_temporary_files_are_not_data(self):
        self.assertEqual(catalog.modality("folder/~$report.docx"), "restricted_or_non_data")
        self.assertEqual(catalog.modality("Thumbs.db"), "restricted_or_non_data")
    def test_explicit_basin_header_evidence(self):
        self.assertEqual(catalog.geography({"CTRY": {"value": "NG"}}, "# Project: NIGER_DELTA_MID", "")[0], "source_header_niger_delta")
    def test_credential_file_is_not_training_data(self):
        self.assertEqual(catalog.modality("Volve dataset credentials.txt"), "restricted_or_non_data")
    def test_seismic_not_well_label_training(self):
        self.assertNotIn("lithology", catalog.candidates("seismic"))
    def test_country_missing_does_not_invent_external_origin(self):
        self.assertEqual(catalog.geography({}, "", "other/log.las")[0], "unknown")
    def test_field_proposals_are_disjoint_and_deterministic(self):
        records = [{"field": f"field{i}", "well": f"well{i}", "geography_status": "source_header_niger_delta"} for i in range(10)]
        a = catalog.proposed_fields(records)
        self.assertEqual(a, catalog.proposed_fields(list(reversed(records))))
        self.assertEqual(set(a.values()), {"train", "validation", "test"})
        self.assertEqual(len(a), 10)
    def test_insufficient_fields_yield_no_split(self):
        self.assertEqual(catalog.proposed_fields([{"field":"A","well":"1","geography_status":"source_header_niger_delta"}]), {})
    def test_las_header_stops_before_samples(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "x.las"
            path.write_text("~W\nWELL. TEST-1 : WELL\nFLD. TEST FIELD : FIELD\nCTRY. NG : COUNTRY\n~C\nGR.API : Gamma ray\n~A\n1 100\n")
            headers, curves, text = catalog.las_header(path)
            self.assertEqual(headers["WELL"]["value"], "TEST-1")
            self.assertEqual(curves[0]["mnemonic"], "GR")
            self.assertNotIn("1 100", text)
if __name__ == "__main__":
    unittest.main()

