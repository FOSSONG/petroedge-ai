import importlib.util,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location("prepare_splits",Path(__file__).parents[1]/"prepare_splits.py")
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

def records():
    return [dict(file_id=str(i),source_path=f"source{i}.csv",sha256=f"{i:064x}",
      field_id=f"field{i}",well_id=f"well{i}",task="porosity",region_status="verified_niger_delta",
      region_evidence="reviewed-header-table",identity_status="verified",label_status="verified",units_status="verified") for i in range(10)]

class SplitTests(unittest.TestCase):
    def test_repeatable_field_split(self):
        rows=records()
        a=module.plan(rows)
        b=module.plan(list(reversed(rows)))
        self.assertEqual({r["file_id"]:r["split"] for r in a},{r["file_id"]:r["split"] for r in b})
        self.assertEqual({r["split"] for r in a},{"train","validation","test"})
    def test_external_nonedge_allowed(self):
        rows=records(); rows[0]["region_status"]="verified_external"
        self.assertEqual(len(module.plan(rows)),10)
    def test_labels_not_assumed(self):
        rows=records(); rows[0]["label_status"]="interpreted_unknown"
        with self.assertRaisesRegex(ValueError,"label provenance"): module.plan(rows)
    def test_geography_is_optional(self):
        rows=records()
        for row in rows:
            row.pop("region_status");row.pop("region_evidence")
        self.assertEqual(len(module.plan(rows)),10)
    def test_duplicate_identity_conflict(self):
        rows=records(); rows[1]["sha256"]=rows[0]["sha256"]
        with self.assertRaisesRegex(ValueError,"Identical"): module.plan(rows)
    def test_well_cannot_cross_fields(self):
        rows=records(); rows[1]["well_id"]=rows[0]["well_id"]
        with self.assertRaisesRegex(ValueError,"canonical well"): module.plan(rows)
    def test_insufficient_fields_rejected(self):
        with self.assertRaisesRegex(ValueError,"three independent"): module.plan(records()[:2])
    def test_edge_needs_causal_review(self):
        rows=records()
        for r in rows: r.update(task="edge_computing",region_status="verified_external")
        with self.assertRaisesRegex(ValueError,"causal"): module.plan(rows)
        for r in rows:r["causal_review"]="verified"
        self.assertEqual(len(module.plan(rows)),10)
    def test_changed_source_fails_closed(self):
        rows=records()
        with self.assertRaisesRegex(ValueError,"Missing reviewed source"):module.validate(rows)
if __name__=="__main__":unittest.main()

