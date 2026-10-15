import datetime as dt
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'.agents/skills/z24-race-manager/scripts'))
from race_laps import crossing,summarize,CST
class LapTests(unittest.TestCase):
 def rows(self):
  start=dt.datetime(2025,12,20,16,tzinfo=CST)
  return [dict(id=i,laps=i,lapTm=60000,ri_time_of_day=(start+dt.timedelta(minutes=i)).strftime('%Y/%m/%d %H:%M:%S'),timeOfDay=(start+dt.timedelta(minutes=i)).strftime('%H:%M:%S')+'.123') for i in range(1,21)]
 def test_cutoff_no_future(self):
  rows,stats=summarize(self.rows(),dt.datetime(2025,12,20,16,10,30,tzinfo=CST))
  self.assertEqual(len(rows),10);self.assertEqual(stats['laps_at_cutoff'],10)
  self.assertEqual(stats['pace_median_seconds'],60);self.assertEqual(stats['pit_loss_equivalent_laps'],3)
  self.assertAlmostEqual(stats['crossing_age_seconds'],29.877)
 def test_long_lap_excluded_and_stale_phase(self):
  rows=self.rows();rows[-1]['lapTm']=240000
  _,s=summarize(rows,dt.datetime(2025,12,20,16,25,tzinfo=CST))
  self.assertEqual(s['excluded_recent_laps'],1);self.assertFalse(s['phase_estimate_usable'])
 def test_time_conflict_rejected(self):
  item=self.rows()[0];item['timeOfDay']='17:00:00.000'
  with self.assertRaises(ValueError):crossing(item)
 def test_before_first_lap(self):
  rows,s=summarize(self.rows(),dt.datetime(2025,12,20,16,tzinfo=CST))
  self.assertEqual(rows,[]);self.assertEqual(s['status'],'no_laps_before_cutoff')

class LapCsvTests(unittest.TestCase):
 def test_cli_replaces_laps_and_cutoff_analysis(self):
  import tempfile,json
  from unittest.mock import patch
  import race_laps
  from race_live_common import data_folder,endpoint_once
  from race_data.csv_io import read_csv
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder)
   config=dict(token='laps-run',team='A',mode='test',output=str(root),selected=dict(ssid=262,race_id=1,round_id=2,pid=3,start_time='2025/12/20 16:00:00'))
   path=data_folder(config)
   endpoint_once(config,'all_class',lambda *a,**k:dict(flag=1,round=dict(id=3),items=[dict(id=1,carNo='025',carTeam='A')]))
   active=root/'active.json';active.write_text(json.dumps(dict(token='laps-run',data_output=str(path))))
   args=['race_laps.py','--active',str(active),'--run-id','laps-run','--team','A','--at','2025-12-20T16:10:30+08:00']
   payload=dict(flag=1,items=LapTests().rows())
   with patch.object(sys,'argv',args),patch.object(race_laps,'read',return_value=payload),patch('builtins.print'):
    race_laps.main();race_laps.main()
   envelope,rows=read_csv(path/'laps.csv','laps-run','laps')
   self.assertEqual(len(rows),10)
   pace,stats=read_csv(path/'pace.csv','laps-run','pace')
   self.assertEqual(stats[0].pace_median_seconds,60)
   self.assertEqual(envelope.snapshot_id,pace.snapshot_id)
   with patch.object(sys,'argv',args),patch.object(race_laps,'read',side_effect=OSError('offline')),patch('builtins.print'):race_laps.main()
   _,stats=read_csv(path/'pace.csv','laps-run','pace')
   self.assertEqual(stats[0].status,'error')
   self.assertEqual(read_csv(path/'laps.csv')[1],[])
