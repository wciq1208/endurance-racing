import datetime as dt
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'.agents/skills/z24-race-manager/scripts'))
import race_weather as w
import race_live as live
from PIL import Image

class WeatherWorkerTests(unittest.TestCase):
 def test_skill_explicitly_passes_location(self):
  config=dict(weather=dict(live.VENUE_WEATHER),output='/example',token='run',mode='test',interval=30)
  cmd=live.worker_command('weather',Path('/config'),config)
  self.assertEqual(cmd[cmd.index('--lat')+1],'27.8206')
  self.assertEqual(cmd[cmd.index('--lon')+1],'113.062648')
  self.assertNotIn('--config',cmd)
 def test_alternative_venue_reaches_collector_and_image(self):
  with tempfile.TemporaryDirectory() as folder:
   a=SimpleNamespace(output=Path(folder),lat=39.04,lon=117.72,station='az9220',location='测试天津',token='abc',mode='test')
   def collect(args):
    self.assertEqual((args.lat,args.lon,args.station),(39.04,117.72,'az9220'))
    self.assertIn('测试天津',args.case_label)
    args.output.mkdir();Image.new('RGB',(20,20)).save(args.output/'chart.png')
    return {'collected_at':w.now(),'radar':{'ok':True,'chart':'chart.png','nowcast':{'source_time':w.now(),'available':False}}}
   with patch('weather_radar_collect.collect',side_effect=collect):w.once(a)
   with Image.open(a.output/'radar.png') as im:
    self.assertEqual(im.info['lat'],'39.04');self.assertEqual(im.info['location'],'测试天津')
    self.assertEqual(im.info['run_id'],'abc')
 def test_cleanup_leaves_other_skill(self):
  with tempfile.TemporaryDirectory() as folder:
   state=Path(folder)/'.runtime/z24-race-manager';out=state/'outputs';out.mkdir(parents=True)
   other=state.parent/'other/outputs';other.mkdir(parents=True);(other/'keep.csv').write_text('keep')
   (out/'old.csv').write_text('old')
   with patch.object(live,'STATE',state),patch.object(live,'OUTPUTS',out):live.clear_outputs()
   self.assertTrue((other/'keep.csv').exists());self.assertEqual(list(out.iterdir()),[])
