"""Exercise real detached start/restart/stop without contacting race/weather APIs."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.agents/skills/z24-race-manager/scripts'))
import race_process


class LifecycleTests(unittest.TestCase):
    def test_restart_clears_old_resources_and_stops_all_lanes(self):
        with tempfile.TemporaryDirectory(prefix='赛车 space ') as folder:
            root=Path(folder)
            skills=root/'.agents/skills/z24-race-manager/scripts'
            shutil.copytree(ROOT/'.agents/skills/z24-race-manager/scripts',skills,ignore=shutil.ignore_patterns('__pycache__'))
            shutil.copytree(ROOT/'race_data',root/'race_data',ignore=shutil.ignore_patterns('__pycache__'))
            shutil.copytree(ROOT/'scripts',root/'scripts',ignore=shutil.ignore_patterns('__pycache__'))
            # Real supervisor/launcher/lock/shutdown; deterministic offline workers.
            worker="""import argparse,json,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--config');p.add_argument('--output');p.add_argument('--token');a,_=p.parse_known_args()
out=Path(a.output) if a.output else Path(json.loads(Path(a.config).read_text(encoding='utf-8'))['output'])
(out/(Path(__file__).stem+'.ready')).write_text(a.token,encoding='utf-8')
time.sleep(90)
"""
            workers=[skills/'race_all_class.py',skills/'race_control_message.py',root/'scripts/race_weather.py']
            for path in workers:path.write_text(worker,encoding='utf-8')
            fixture=root/'fixture.json';shutil.copyfile(ROOT/'tests/fixtures/discovery-2025.json',fixture)
            launcher=skills/'race_live.py'
            env={**os.environ,'PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8'}
            def run(*args):
                result=subprocess.run([sys.executable,str(launcher),*args],cwd=root,env=env,capture_output=True,text=True,encoding='utf-8',timeout=30)
                self.assertEqual(result.returncode,0,result.stderr)
                return result.stdout
            def start():
                state=json.loads(run('start','--mode','test','--team','中文车队','--discovery',str(fixture)))
                deadline=time.monotonic()+10
                while len(list(Path(state['output']).glob('*.ready')))<3 and time.monotonic()<deadline:time.sleep(.05)
                self.assertEqual(len(list(Path(state['output']).glob('*.ready'))),3)
                return state
            states=[]
            try:
                first=start();states.append(first)
                config=json.loads(Path(first['config']).read_text(encoding='utf-8'))
                self.assertEqual(config['interval'],60)
                self.assertEqual(config['weather_interval'],120)
                self.assertTrue(json.loads(run('status'))['running'])
                second=start();states.append(second)
                self.assertNotEqual(first['token'],second['token'])
                self.assertFalse(Path(first['output']).exists())
                self.assertFalse(Path(first['data_output']).exists())
                public=Path(second['data_output']).parent/'active.json'
                manifest=json.loads(public.read_text(encoding='utf-8'))
                self.assertEqual(manifest['run']['run_id'],second['token'])
                self.assertNotIn('config',manifest)
                self.assertFalse(race_process.owned_processes(first,[launcher,*workers]))
                run('stop')
                self.assertFalse(json.loads(run('status'))['running'])
                self.assertFalse(public.exists())
                self.assertFalse(race_process.owned_processes(second,[launcher,*workers]))
            finally:
                for state in states:race_process.stop_owned(state,[launcher,*workers])
