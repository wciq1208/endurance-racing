import datetime as dt
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'.agents/skills/z24-race-manager/scripts'))
from race_clock import race_clock,CST

class RaceClockTests(unittest.TestCase):
 def test_cycle_hours(self):
  for hour,elapsed in [(17,1),(2,10),(15,23),(16,0)]:
   result=race_clock(dt.datetime(2026,10,12,hour,tzinfo=CST))
   self.assertEqual(result['elapsed_hours'],elapsed)
   self.assertEqual(result['remaining_hours'],24-elapsed)
 def test_finish_overrides_new_cycle(self):
  result=race_clock(dt.datetime(2026,10,12,16,tzinfo=CST),finished=True)
  self.assertEqual(result['elapsed_seconds'],86400);self.assertEqual(result['remaining_seconds'],0)
 def test_timezone_conversion(self):
  result=race_clock(dt.datetime(2026,10,12,18,tzinfo=dt.timezone.utc))
  self.assertEqual(result['elapsed_hours'],10)
