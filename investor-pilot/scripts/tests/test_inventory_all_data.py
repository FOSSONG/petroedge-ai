import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parents[1]))
from inventory_all_data import identify,classify,routes,restricted
class InventoryTests(unittest.TestCase):
    def test_las_with_wrong_extension(self):
        self.assertEqual(identify(Path("well.dat"),b"# PETREL\n~Version\n VERS. 2.0\n~Well\n")[0],"LAS_ASCII")
    def test_pvt_underscore_path(self):
        self.assertIn("pvt_fluids",classify("PVT_Composition/pvt.csv","CSV"))
    def test_second_line_production_header(self):
        self.assertIn("production",classify("unknown.csv","CSV","Well-01\nDate,Qoil,Qgas,Qwat\n"))
    def test_binary_petrel_components(self):
        self.assertEqual(identify(Path("a.ptd"),b"\xff\xffFloatWellLog")[0],"PETREL_WELL_LOG")
        self.assertEqual(identify(Path("a.ptd"),b"\xff\xffWellTrace3")[0],"PETREL_TRAJECTORY")
    def test_plot_not_numerical_format(self):
        self.assertEqual(identify(Path("a.pds"),b"Pds Spec 2.9")[0],"PDS_PLOT")
    def test_secret_not_opened(self):
        self.assertTrue(restricted(Path("Volve dataset credentials.txt")))
    def test_geography_does_not_change_log_routes(self):
        self.assertEqual(routes(classify("Norway/well.las","LAS_ASCII")),routes(classify("Niger Delta/well.las","LAS_ASCII")))
    def test_archive_filename_encoding_is_preserved(self):
        import tempfile
        from inventory_all_data import writecsv
        with tempfile.TemporaryDirectory(dir=r"E:\PETROEDGE_AI\codex\runtime\tmp") as d:
            p=Path(d)/"members.csv"
            writecsv(p,[{"member":"bad"+chr(0xdc8a)+"name"}])
            self.assertIn(r"\udc8a",p.read_text(encoding="utf-8-sig"))
    def test_unknown_stays_unclassified(self):
        self.assertEqual(classify("x.blob","BLOB"),["unclassified"])
if __name__=="__main__":unittest.main()
