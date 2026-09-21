import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
from qualify_log_core import measurement,canon_freeman,freeman_rows,feature_issues
from review_source_identities import header_identity
from extract_core_readiness import extract
class QualificationTests(unittest.TestCase):
    def test_censored_value_is_not_zero_or_detection_limit(self):
        r=measurement("<0.01")
        self.assertEqual(r["kind"],"censored")
        self.assertIsNone(r["value"])
        self.assertEqual(r["bound"],.01)
        self.assertEqual(r["operator"],"<")
    def test_missing_and_exact_zero_are_distinct(self):
        self.assertEqual(measurement("")["kind"],"missing")
        self.assertEqual(measurement("0")["kind"],"exact")
        self.assertEqual(measurement("0")["value"],0)
    def test_error_or_nonfinite_is_not_numeric_target(self):
        for x in ["#DIV/0!","NMP",float("nan")]:
            self.assertEqual(measurement(x)["kind"],"non_numeric")
    def test_sidetrack_identity_is_preserved(self):
        self.assertEqual(canon_freeman("Freeman-004"),"FREEMAN-4")
        self.assertEqual(canon_freeman(": Freeman-4 ST1"),"FREEMAN-4-ST1")
        self.assertNotEqual(canon_freeman("Freeman-4"),canon_freeman("Freeman-4ST1"))
        self.assertNotEqual(canon_freeman("Freeman-2ST1"),canon_freeman("Freeman-2ST3"))
        self.assertIsNone(canon_freeman("AnotherField-4"))
    def test_repeated_well_headers_partition_one_sheet(self):
        b={"sheets":[{"name":"Corelab Poroperm","rows":[["WELL ID",": Freeman-4"],[1,8300,10,5,20,2.65,"sst"],["WELL ID",": Freeman-4 ST1"],[1,8500,20,10,25,2.65,"sst"]]}]}
        r=list(freeman_rows(b))
        self.assertEqual([x["well"] for x in r],["FREEMAN-4","FREEMAN-4-ST1"])
    def test_legacy_extractor_also_respects_repeated_headers(self):
        rows=[[] for _ in range(10)]+[[1,8300,10,5,20,2.65,"sst"],["WELL ID",": Freeman-4 ST1"],[1,8500,20,10,25,2.65,"sst"]]
        b={"source_path":"Freeman-4 conventional core analysis.xls","file_id":"f","sha256":"s","collection":"c","sheets":[{"name":"Corelab Poroperm","rows":rows}]}
        r,_,_=extract(b)
        self.assertEqual([x["well_source"] for x in r],["Freeman-4","Freeman-4ST1"])
    def test_agreeing_duplicate_las_well_headers_are_recovered(self):
        h={"WELL:1":{"value":"X-001"},"WELL:2":{"value":"X-001"}}
        self.assertEqual(header_identity(h,"WELL")[:2],("X-001","consistent_source_header"))
    def test_conflicting_duplicate_headers_fail_closed(self):
        h={"WELL:1":{"value":"X-001"},"WELL:2":{"value":"X-002"}}
        self.assertEqual(header_identity(h,"WELL")[:2],("","conflicting_source_headers"))
    def test_invalid_inputs_are_not_imputed(self):
        r=feature_issues({"gr_api":20,"bulk_density_g_cm3":2.3,"neutron_porosity_v_v":None,"deep_resistivity_ohm_m":0})
        self.assertIn("missing_neutron_porosity_v_v",r)
        self.assertIn("nonpositive_deep_resistivity_ohm_m",r)
if __name__=="__main__":unittest.main()
