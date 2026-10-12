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
