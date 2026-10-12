import datetime as dt
from pathlib import Path
import sys
import unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import weather_radar_collect as m

class RadarTests(unittest.TestCase):
 def test_jsonp_not_executed(self):
  self.assertEqual(m.jsonp('callback({"x":1});','callback'),{'x':1})
  with self.assertRaises(ValueError):m.jsonp('callback({});alert(1)','callback')
 def test_shift_direction(self):
  a=np.zeros((100,100,4),dtype=np.uint8);a[25:50,30:55,3]=255;a[40:50,55:70,3]=255
  b=m.advect(a,4,-3);shift,score=m.estimate_shift(a,b)
  np.testing.assert_allclose(shift,[4,-3]);self.assertGreater(score,.99)
 def test_no_wrap(self):
  a=np.zeros((20,20,4),dtype=np.uint8);a[:,18:,3]=255
  self.assertEqual(m.advect(a,5,0)[...,3].sum(),0)
 def test_sparse_echo_rejected(self):
  a=np.zeros((100,100,4),dtype=np.uint8)
  with self.assertRaises(ValueError):m.estimate_shift(a,a)
 def test_stale_rejected(self):
  frames=[{'dt':'202610121000'},{'dt':'202610121006'},{'dt':'202610121012'}]
  with self.assertRaises(ValueError):m.motion(frames,[],dt.datetime(2026,10,12,11,tzinfo=m.CST))
 def test_irregular_gaps_and_delayed_source(self):
  a=np.zeros((180,180,4),dtype=np.uint8);a[40:70,40:70,3]=255;a[60:70,70:80,3]=255
  offsets=[0,6,11,17,22,28]
  start=dt.datetime(2026,10,12,17,tzinfo=m.CST)
  frames=[{'dt':(start+dt.timedelta(minutes=t)).strftime('%Y%m%d%H%M')} for t in offsets]
  arrays=[m.advect(a,t,-t) for t in offsets]
  speed,score=m.motion(frames,arrays,start+dt.timedelta(minutes=46))
  np.testing.assert_allclose(speed,[1,-1]);self.assertGreater(score,.99)
 def test_inconsistent_motion_rejected(self):
  a=np.zeros((180,180,4),dtype=np.uint8);a[70:100,70:100,3]=255
  frames=[{'dt':'202610121700'},{'dt':'202610121706'},{'dt':'202610121712'}]
  arrays=[a,m.advect(a,18,0),a]
  with self.assertRaises(ValueError):m.motion(frames,arrays,dt.datetime(2026,10,12,17,30,tzinfo=m.CST))
 def test_source_time_is_beijing(self):
  self.assertEqual(m.frame_time({'dt':'202610121200'}).hour,12)

if __name__=='__main__':unittest.main()
