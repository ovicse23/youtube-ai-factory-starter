import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT=pathlib.Path(__file__).resolve().parents[1]

class FactoryTests(unittest.TestCase):
    def test_sample_schema(self):
        sys.path.insert(0,str(ROOT))
        import factory
        obj=json.loads((ROOT/"examples/sample-episode.json").read_text())
        self.assertTrue(factory.check_episode(obj))
        self.assertEqual(len(obj['scenes']),3)

    def test_cli_help(self):
        res=subprocess.run([sys.executable,str(ROOT/"factory.py"),"--help"],capture_output=True,text=True)
        self.assertEqual(res.returncode,0)
        self.assertIn('render',res.stdout)

    def test_missing_episode_raises(self):
        sys.path.insert(0,str(ROOT))
        import factory
        with self.assertRaises(SystemExit):
            factory.read_episode("missing-episode-xyz")

if __name__ == "__main__": unittest.main()
