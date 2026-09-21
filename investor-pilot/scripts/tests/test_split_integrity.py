import unittest
from test_prepare_splits import records, module

class SplitIntegrityTests(unittest.TestCase):
    def test_uppercase_checksum_cannot_hide_duplicate(self):
        rows=records()
        rows[0]["sha256"]="ab"*32
        rows[1]["sha256"]="AB"*32
        with self.assertRaisesRegex(ValueError,"Identical"):module.plan(rows)
    def test_duplicate_within_same_well_is_not_weighted_twice(self):
        rows=records()
        rows.append(dict(rows[0],file_id="copy"))
        with self.assertRaisesRegex(ValueError,"Identical"):module.plan(rows)
    def test_invalid_digest_is_rejected(self):
        rows=records();rows[0]["sha256"]="not-a-hash"
        with self.assertRaisesRegex(ValueError,"SHA-256"):module.plan(rows)

