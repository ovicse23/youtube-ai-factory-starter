import json
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from upload_timing import compute_upload_windows, format_upload_plan, validate_timezone


class UploadTimingTests(unittest.TestCase):
    def test_shorts_windows_dst_october(self):
        plan = compute_upload_windows(
            aspect="9:16",
            target_countries=["US", "UK", "CA", "AU"],
            creator_tz="Asia/Dhaka",
            ref_date="2026-10-23",
        )
        self.assertEqual(plan["aspect"], "9:16")
        self.assertEqual(len(plan["slots"]), 2)
        primary = plan["slots"][0]
        # On 2026-10-23: US is EDT (UTC-4), UK is BST (UTC+1), Asia/Dhaka is +06
        # 12:00-14:00 EDT = 16:00-18:00 UTC = 17:00-19:00 BST = 22:00-00:00 (+1d) +06
        self.assertIn("16:00–18:00", primary["markets"]["UTC"]["public_publish"])
        self.assertIn("12:00–14:00", primary["markets"]["US Eastern (ET)"]["public_publish"])
        self.assertIn("17:00–19:00", primary["markets"]["United Kingdom"]["public_publish"])
        self.assertIn("22:00–00:00", primary["creator_local"]["public_publish"])

    def test_longform_windows_winter(self):
        plan = compute_upload_windows(
            aspect="16:9",
            target_countries=["US", "UK", "CA"],
            creator_tz="Asia/Dhaka",
            ref_date="2026-01-15",
        )
        self.assertEqual(plan["aspect"], "16:9")
        primary = plan["slots"][0]
        # On 2026-01-15: US is EST (UTC-5), UK is GMT (UTC+0)
        # 13:00-15:00 EST = 18:00-20:00 GMT
        self.assertIn("18:00–20:00", primary["markets"]["United Kingdom"]["public_publish"])

    def test_invalid_timezone_rejected(self):
        with self.assertRaises(ValueError):
            validate_timezone("Not/AZone")

    def test_cli_upload_plan_json(self):
        res = subprocess.run(
            [sys.executable, str(ROOT / "factory.py"), "upload-plan", "--aspect", "9:16", "--date", "2026-10-23", "--json"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        payload = json.loads(res.stdout)
        self.assertEqual(payload["reference_date"], "2026-10-23")
        self.assertIn("US", payload["target_countries"])

    def test_format_upload_plan_contains_sources(self):
        text = format_upload_plan(aspect="9:16", target_countries=["US", "UK"], creator_tz="UTC", ref_date="2026-10-23")
        self.assertIn("TOP-TIER COUNTRY UPLOAD & SCHEDULE PLAN", text)
        self.assertIn("https://buffer.com/resources/best-time-to-post-on-youtube/", text)
        self.assertIn("When your viewers are on YouTube", text)


if __name__ == "__main__":
    unittest.main()
