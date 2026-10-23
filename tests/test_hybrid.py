import json
import pathlib
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dashboard import make_handler
from hybrid_store import HybridStore


class HybridControlCenterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = pathlib.Path(self.tmp.name)
        (self.ws / "episodes" / "pilot-01").mkdir(parents=True)
        sample_ep = json.loads((ROOT / "episodes" / "pilot-01" / "episode.json").read_text(encoding="utf-8"))
        (self.ws / "episodes" / "pilot-01" / "episode.json").write_text(
            json.dumps(sample_ep, indent=2), encoding="utf-8"
        )
        self.store = HybridStore(db_path=self.ws / ".local" / "factory.db", workspace_root=self.ws)

    def tearDown(self):
        self.tmp.cleanup()

    def test_bootstrap_and_seed_modules(self):
        snap = self.store.bootstrap()
        self.assertEqual(snap["runtime"], "local_engine")
        self.assertGreaterEqual(len(snap["channels"]), 2)
        self.assertGreaterEqual(len(snap["ideas"]), 5)
        self.assertGreaterEqual(len(snap["videos"]), 1)
        self.assertIn("pilot-01", snap["approvals"])

    def test_promote_idea_writes_episode_and_prompts(self):
        promoted = self.store.promote_idea("idea-airplane-window", custom_slug="pilot-02-window")
        self.assertEqual(promoted["slug"], "pilot-02-window")
        self.assertEqual(len(promoted["scenes"]), 3)
        ep_file = self.ws / "episodes" / "pilot-02-window" / "episode.json"
        prompt_file = self.ws / "episodes" / "pilot-02-window" / "prompts" / "scene-01.txt"
        self.assertTrue(ep_file.is_file())
        self.assertTrue(prompt_file.is_file())
        self.assertIn("GLOBAL CONTINUITY:", prompt_file.read_text(encoding="utf-8"))

    def test_credit_and_publish_gate_invariants(self):
        # Cannot approve remaining Digen scenes before Scene 1 credit gate
        with self.assertRaises(ValueError):
            self.store.upsert_approval({"video_slug": "pilot-01", "digen_remaining_approved": True})
        # Cannot approve Private YouTube upload before QA gate passes
        with self.assertRaises(ValueError):
            self.store.upsert_approval({"video_slug": "pilot-01", "private_upload_approved": True})

        # Unapproved Digen job enters awaiting_approval
        blocked_job = self.store.enqueue_job({"video_slug": "pilot-01", "job_type": "digen_scene_01"})
        self.assertEqual(blocked_job["status"], "awaiting_approval")

        # Approve Scene 1 -> queued Digen job becomes runnable
        self.store.upsert_approval({"video_slug": "pilot-01", "digen_scene1_approved": True})
        ready_job = self.store.enqueue_job({"video_slug": "pilot-01", "job_type": "digen_scene_01"})
        self.assertEqual(ready_job["status"], "queued")

    def test_analytics_updates_studio_heatmap_override(self):
        rec = self.store.upsert_analytics(
            {
                "channel_id": "ch-hawthorn",
                "video_slug": "pilot-01",
                "views_48h": 14200,
                "viewed_vs_swiped_pct": 76.4,
                "avg_completion_pct": 91.2,
                "top_country": "US",
                "studio_heatmap_peak": "Thu 21:30 Asia/Dhaka",
            }
        )
        self.assertEqual(rec["views_48h"], 14200)
        ch = next(c for c in self.store.list_channels() if c["id"] == "ch-hawthorn")
        self.assertEqual(ch["studio_heatmap_override"], "Thu 21:30 Asia/Dhaka")

    def test_channel_incubator_and_adoption(self):
        # 1. Research niche package
        pkg = self.store.incubate_channel(topic="Everyday Hidden Mechanics")
        self.assertIn("Everyday Hidden Mechanics", pkg["name"])
        self.assertTrue(pkg["handle"].startswith("@"))
        self.assertTrue(len(pkg["description"]) > 50)
        self.assertGreaterEqual(len(pkg["keywords"]), 5)
        self.assertTrue(len(pkg["avatar_prompt"]) > 30)
        self.assertTrue(len(pkg["banner_prompt"]) > 30)
        self.assertGreaterEqual(len(pkg["viral_concepts"]), 1)

        # 2. Adopt channel and launch Video #1
        res = self.store.adopt_incubated_channel(pkg, concept_index=0)
        ch = res["channel"]
        ep = res["episode"]
        idea = res["idea"]

        self.assertEqual(ch["name"], pkg["name"])
        self.assertEqual(ch["avatar_prompt"], pkg["avatar_prompt"])
        self.assertEqual(idea["channel_id"], ch["id"])

        # Check episode files written locally
        ep_dir = self.ws / "episodes" / ep["slug"]
        self.assertTrue((ep_dir / "episode.json").is_file())
        self.assertTrue((ep_dir / "prompts" / "scene-01.txt").is_file())
        self.assertTrue((ep_dir / "upload-schedule.txt").is_file())
        self.assertTrue((ep_dir / "seo-package.txt").is_file())

        # Check episode is listed in store videos
        all_vids = self.store.list_videos()
        self.assertTrue(any(v["slug"] == ep["slug"] for v in all_vids))

    def test_http_endpoints_and_media_upload(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.store))
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{port}"
        try:
            # HTML index serves all 6 hybrid modules
            with urllib.request.urlopen(f"{base}/") as r:
                html = r.read().decode("utf-8")
                self.assertIn("Channels", html)
                self.assertIn("Research Provider", html)
                self.assertIn("Approvals", html)
                self.assertIn("Analytics", html)

            # Cross-origin POST is rejected
            bad_req = urllib.request.Request(
                f"{base}/api/channels",
                data=b'{"name":"Evil"}',
                method="POST",
                headers={"Content-Type": "application/json", "Origin": "https://evil.example"},
            )
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(bad_req)
            self.assertEqual(ctx.exception.code, 403)

            # Media PUT + GET round-trip into episodes/pilot-01/clips/scene-01.mp4
            put_req = urllib.request.Request(
                f"{base}/api/media/pilot-01/scene-01.mp4",
                data=b"\x00\x00\x00\x18ftypmp42",
                method="PUT",
                headers={"Content-Type": "video/mp4", "Origin": base},
            )
            with urllib.request.urlopen(put_req) as r:
                out = json.loads(r.read().decode("utf-8"))
                self.assertTrue(out["ok"])
            with urllib.request.urlopen(f"{base}/api/media/pilot-01/scene-01.mp4") as r:
                self.assertEqual(r.read(), b"\x00\x00\x00\x18ftypmp42")
            # Incubator GET endpoint
            with urllib.request.urlopen(f"{base}/api/channels/incubate?topic=Miniature+Diorama") as r:
                inc_data = json.loads(r.read().decode("utf-8"))
                self.assertIn("name", inc_data)
                self.assertIn("description", inc_data)
                self.assertIn("avatar_prompt", inc_data)
                self.assertIn("viral_concepts", inc_data)

            # Incubator POST endpoint (adopt & launch)
            adopt_req = urllib.request.Request(
                f"{base}/api/channels/incubate",
                data=json.dumps({"package": inc_data, "concept_index": 0}).encode("utf-8"),
                method="POST",
                headers={"Content-Type": "application/json", "Origin": base},
            )
            with urllib.request.urlopen(adopt_req) as r:
                adopt_res = json.loads(r.read().decode("utf-8"))
                self.assertIn("channel", adopt_res)
                self.assertIn("episode", adopt_res)
                self.assertEqual(adopt_res["channel"]["name"], inc_data["name"])
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
