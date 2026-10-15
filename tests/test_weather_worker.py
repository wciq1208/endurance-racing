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
  config=dict(weather=dict(live.VENUE_WEATHER),output='/example',token='run',mode='test',interval=60)
  cmd=live.worker_command('weather',Path('/config'),config)
  self.assertEqual(cmd[cmd.index('--lat')+1],'27.8206')
  self.assertEqual(cmd[cmd.index('--lon')+1],'113.062648')
  self.assertNotIn('--config',cmd)
  self.assertEqual(float(cmd[cmd.index('--interval')+1]),120)
  config['weather_interval']=180
  cmd=live.worker_command('weather',Path('/config'),config)
  self.assertEqual(float(cmd[cmd.index('--interval')+1]),180)
  self.assertEqual(live.lane_interval(config,'all_class'),60)
  self.assertEqual(live.lane_interval(config,'control_message'),60)
 def test_alternative_venue_reaches_collector_and_image(self):
  with tempfile.TemporaryDirectory() as folder:
   a=SimpleNamespace(output=Path(folder),lat=39.04,lon=117.72,station='az9220',location='测试天津',token='abc',mode='test')
   def collect(args):
    self.assertEqual((args.lat,args.lon,args.station),(39.04,117.72,'az9220'))
    self.assertIn('测试天津',args.case_label)
    args.output.mkdir();Image.new('RGB',(20,20)).save(args.output/'chart.png')
    return {'collected_at':w.now(),'radar':{'ok':True,'chart':'chart.png','nowcast':{'source_time':w.now(),'available':False}}}
   from race_data.csv_io import initialize_run,read_csv
   a.data_output=Path(folder)/'public'
   initialize_run(a.data_output,dict(token='abc',team='测试车队',mode='test',selected=dict(ssid=262,race_id=1,round_id=2,pid=3)))
   with patch('weather_radar_collect.collect',side_effect=collect):w.once(a)
   envelope,rows=read_csv(a.data_output/'weather.csv','abc','weather')
   self.assertEqual(len(rows),1)
   self.assertEqual(envelope.collection.status,'ok')
   with Image.open(a.data_output/'radar.png') as im:
    self.assertEqual(im.info['lat'],'39.04');self.assertEqual(im.info['location'],'测试天津')
    self.assertEqual(im.info['run_id'],'abc')
