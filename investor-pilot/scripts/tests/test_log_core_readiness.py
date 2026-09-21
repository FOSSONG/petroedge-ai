import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
from profile_log_core import family,depth_factor,stats
from match_log_core import norm,shift_depth
from extract_core_readiness import extract
class ReadinessTests(unittest.TestCase):
    def test_composite_curves_are_recognized(self):
        self.assertEqual(family("GR_COMP"),"gamma_ray")
        self.assertEqual(family("RDEEP_COMP"),"resistivity")
        self.assertEqual(family("PHIE"),"")
    def test_depth_units(self):
        self.assertAlmostEqual(depth_factor("0.1 in"),.00254)
        self.assertAlmostEqual(depth_factor("FT"),.3048)
        self.assertIsNone(depth_factor(""))
    def test_sentinels_separate_from_finite_values(self):
        r=stats([10.,-999.25,float("nan"),20.])
        self.assertEqual(r["nonfinite"],1);self.assertEqual(r["suspected_sentinel"],1)
        self.assertEqual(r["usable_candidate_count"],2)
    def test_identity_preserves_sidetracks_and_alias_conflicts(self):
        self.assertEqual(norm("15/9-19 A"),norm("15_9-19A"))
        self.assertNotEqual(norm("Freeman-2"),norm("Freeman-2ST1"))
        self.assertNotEqual(norm("X-001"),norm("XX-001"))
    def test_shift_sign_and_bounds(self):
        sample={"depth_unit":"m","core_depth":3700,"well_source":"GABO51","core_id_source":""}
        shifts=[{"well":"GABO-51","core_id":"CORE 1","core_top_m":3688,"core_base_m":3718.58,"log_top_m":3691.15,"log_base_m":3721.73}]
        self.assertAlmostEqual(shift_depth(sample,shifts)[0],3703.15)
        sample["core_depth"]=3800
        self.assertIsNone(shift_depth(sample,shifts)[0])
    def test_unknown_units_never_assumed(self):
        self.assertEqual(shift_depth({"depth_unit":"","core_depth":1000},[])[1],"depth_unit_unresolved")
    def test_ambiguous_overlapping_shifts_are_not_picked(self):
        s={"depth_unit":"m","core_depth":10,"well_source":"A","core_id_source":""}
        x={"well":"A","core_id":"","core_top_m":0,"core_base_m":20,"log_top_m":1,"log_base_m":21}
        self.assertEqual(shift_depth(s,[x,x])[1],"shift_ambiguous")
    def test_workbook_summary_counts_are_not_core_samples(self):
        rows=[[] for _ in range(6)]+[[1,"GABO-12",2500,"H",.2,10,"","", ""]]+[["","GABO-12, Depth Difference between core and Log is +4.3m"]]+[["","",198,"",184,149]]
        book={"source_path":"GABO12-13-CoreDB_student.xls","file_id":"f","sha256":"s","collection":"c","sheets":[{"name":"CoreDB","rows":rows}]}
        samples,_,_=extract(book)
        self.assertEqual(len(samples),1);self.assertEqual(samples[0]["well_source"],"GABO-12")
    def test_different_stress_measurements_are_retained(self):
        row=[1,3688.3,22,3000,20,2000,2.65,"","Sandstone"]
        book={"source_path":"GABO-51 PRELIMINARY.xls","file_id":"f","sha256":"s","collection":"c","sheets":[{"name":"RR","rows":[[] for _ in range(9)]+[row]}]}
        samples,_,_=extract(book)
        self.assertEqual(len(samples[0]["targets"]),4)
        self.assertNotEqual(samples[0]["targets"][0]["condition"],samples[0]["targets"][2]["condition"])
if __name__=="__main__":unittest.main()
