import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from research_router import DEFAULTS, DIGEN_MCP_ENDPOINT, load_settings, save_settings, route_research, research_instructions, validate

class RouterTests(unittest.TestCase):
    def test_defaults(self):
        with tempfile.TemporaryDirectory() as p:
            s=load_settings(pathlib.Path(p)/'missing.json')
        self.assertEqual(s['research']['provider'],'auto')
        self.assertEqual(s['video']['provider'],'digen')
        self.assertEqual(s['video']['mcp_endpoint'], DIGEN_MCP_ENDPOINT)
        self.assertTrue(s['research']['include_upload_time_research'])
        self.assertTrue(s['publishing']['optimize_top_tier_upload_time'])

    def test_save_round_trip(self):
        with tempfile.TemporaryDirectory() as p:
            dest=pathlib.Path(p)/'settings.json'
            data={'research':{'provider':'gemini','fallback_to_gemini':True}}
            save_settings(data,dest)
            saved=load_settings(dest)
            self.assertEqual(saved['research']['provider'],'gemini')
            self.assertTrue(saved['publishing']['require_approval'])

    def test_no_vidiq_gemini_only(self):
        s=validate({'research':{'provider':'gemini'}})
        result=route_research(s,vidiq_available=True,gemini_available=True)
        self.assertEqual(result['selected'],'gemini')
        text=research_instructions(s)
        self.assertIn('NEVER invoke vidIQ tools',text)
        self.assertIn(DIGEN_MCP_ENDPOINT, text)
        self.assertIn('TOP-TIER COUNTRY UPLOAD & SCHEDULE PLAN', text)

    def test_auto_fallback(self):
        s=validate({'research':{'provider':'auto','fallback_to_gemini':True}})
        self.assertEqual(route_research(s,vidiq_available=True,gemini_available=True)['selected'],'vidiq')
        self.assertEqual(route_research(s,vidiq_available=False,gemini_available=True)['selected'],'gemini')
        self.assertIsNone(route_research(s,vidiq_available=None,gemini_available=True)['selected'])

    def test_strict_vidiq(self):
        s=validate({'research':{'provider':'vidiq','fallback_to_gemini':False}})
        self.assertIsNone(route_research(s,vidiq_available=False,gemini_available=True)['selected'])

    def test_reject_unapproved_production(self):
        with self.assertRaises(ValueError):
            validate({'video':{'provider':'flow'}})
        with self.assertRaises(ValueError):
            validate({'publishing':{'default_visibility':'public'}})
        with self.assertRaises(ValueError):
            validate({'video':{'require_credit_approval':False}})
        with self.assertRaises(ValueError):
            validate({'publishing':{'creator_timezone':'Invalid/Timezone'}})

    def test_cli_show_and_plan(self):
        r=subprocess.run([sys.executable,str(ROOT/'factory.py'),'settings'],capture_output=True,text=True)
        self.assertEqual(r.returncode,0, r.stderr)
        data=json.loads(r.stdout)
        self.assertIn(data['research']['provider'],['auto','vidiq','gemini'])
        r=subprocess.run([sys.executable,str(ROOT/'factory.py'),'research-plan','--topic','Test topic'],capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn('Test topic',r.stdout)

if __name__=='__main__':unittest.main()
