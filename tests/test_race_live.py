import datetime as dt
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'.agents/skills/z24-race-manager/scripts'))
import race_live_common as c
import race_csv_query as q
import race_live as launch

class LiveTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
  self.config={'selected':{'ssid':262,'race_id':1,'round_id':2,'pid':3,'session_status':3},'team':'A','token':'unique-token','output':str(self.root),'interval':30}
 def tearDown(self):self.tmp.cleanup()
 def payload(self):
  return {'flag':1,'round':{'id':3,'ri_end':'2025/12/21 16:00:00'},'items':[{'id':1,'carNo':'025','carTeam':'A','laps':100,'bestTm':61234,'gap':1234}]}
 def test_csv_roundtrip_and_numeric_sql(self):
  c.endpoint_once(self.config,'all_class',lambda *a,**kw:self.payload())
  path=self.root/'all_class.csv';meta,fields,rows=c.read_csv(path)
  self.assertEqual(rows[0]['carNo'],'025');self.assertEqual(meta['pid'],'3')
  self.assertIn('round_end',meta);self.assertEqual(meta['session_status'],'3')
  result=q.query(path,'SELECT carNo, bestTm/1000.0 AS seconds, laps+2 AS projected FROM data')
  self.assertIn('025,61.234,102',result);self.assertIn('query_now',result)
 def test_multiline_control_no_loss(self):
  body='更正,撤销\n"25号"原处罚'
  payload={'flag':1,'round':{'id':3},'items':[{'id':5,'index':2,'cont':body}]}
  c.endpoint_once(self.config,'control_message',lambda *a,**kw:payload)
  _,_,rows=c.read_csv(self.root/'control_message.csv')
  self.assertEqual(rows[0]['cont'],body)
 def test_failure_replaces_success_with_no_stale_rows(self):
  c.endpoint_once(self.config,'all_class',lambda *a,**kw:self.payload())
  c.failure(self.config,'all_class','network\nfailed')
  meta,_,rows=c.read_csv(self.root/'all_class.csv')
  self.assertEqual(meta['status'],'error');self.assertEqual(meta['collected_at'],'');self.assertEqual(rows,[])
  self.assertIn('network failed',meta['error'])
  self.assertEqual(len(list((self.root/'archive/all_class').glob('*.csv'))),1)
 def test_wrong_pid_never_exported(self):
  payload=self.payload();payload['round']['id']=4
  with self.assertRaises(ValueError):c.endpoint_once(self.config,'all_class',lambda *a,**kw:payload)
  self.assertFalse((self.root/'all_class.csv').exists())
 def test_sql_cannot_mutate_or_attach(self):
  c.endpoint_once(self.config,'all_class',lambda *a,**kw:self.payload())
  for sql in ['DELETE FROM data',"ATTACH DATABASE ':memory:' AS other"]:
   with self.assertRaises(sqlite3.DatabaseError):q.query(self.root/'all_class.csv',sql)
 def test_stale_freshness_computed(self):
  meta=c.metadata(self.config,'all_class','ok','2025-01-01T00:00:00+08:00','2025-01-01T00:00:00+08:00')
  c.write_csv(self.root/'a.csv',meta,[],c.FIELDS['all_class'])
  self.assertIn('fresh,false',q.query(self.root/'a.csv','SELECT * FROM data'))
 def test_weather_failure_card_timestamp(self):
  from PIL import Image
  c.failure(self.config,'weather','timeout')
  with Image.open(self.root/'radar.png') as im:
   self.assertEqual(im.info['status'],'error');self.assertTrue(im.info['attempted_at']);self.assertEqual(im.info['collected_at'],'')
 def test_worker_retries_unexpected_errors(self):
  config_path=self.root/'config.json';config_path.write_text(json.dumps(self.config))
  # Fail two consecutive subprocess attempts; the loop survives both.
  with patch.object(sys,'argv',['worker.py','--config',str(config_path),'--token','unique-token']), patch.object(c.subprocess,'run',side_effect=RuntimeError('unexpected')) as run, patch.object(c.time,'sleep',side_effect=[None,KeyboardInterrupt]), patch.object(c.traceback,'print_exc'):
   with self.assertRaises(KeyboardInterrupt):c.worker_main('all_class',lambda config:None)
   self.assertEqual(run.call_count,2)
  self.assertEqual(c.read_csv(self.root/'all_class.csv')[0]['status'],'error')

 def test_failed_stop_never_clears_outputs(self):
  state=self.root/'.runtime';state.mkdir()
  (state/'active.json').write_text(json.dumps({'pid':123,'token':'owned'}))
  with patch.object(launch,'STATE',state), patch.object(sys,'argv',['race_live.py','start','--team','A']), patch('race_doctor.report',return_value={'ready':True,'warnings':[]}), patch.object(launch,'stop_group',side_effect=PermissionError('denied')), patch.object(launch,'clear_outputs') as clear:
   with self.assertRaises(PermissionError):launch.main()
   clear.assert_not_called()
  self.assertTrue((state/'active.json').exists())

 def test_cleanup_only_managed_outputs(self):
  state=self.root/'.runtime';out=state/'outputs';out.mkdir(parents=True)
  (out/'old.csv').write_text('old');(state/'launch.lock').write_text('lock')
  outside=self.root/'keep';outside.mkdir();(outside/'user.txt').write_text('keep')
  try:(out/'linked').symlink_to(outside,target_is_directory=True)
  except OSError:pass  # Windows may require Developer Mode for symlinks
  with patch.object(launch,'STATE',state),patch.object(launch,'OUTPUTS',out):launch.clear_outputs()
  self.assertEqual(list(out.iterdir()),[])
  self.assertTrue((outside/'user.txt').exists());self.assertTrue((state/'launch.lock').exists())
 def test_cleanup_refuses_output_symlink(self):
  state=self.root/'.runtime';state.mkdir();out=state/'outputs'
  outside=self.root/'keep';outside.mkdir()
  try:out.symlink_to(outside,target_is_directory=True)
  except OSError:self.skipTest('Symlinks require Windows Developer Mode')
  with patch.object(launch,'STATE',state),patch.object(launch,'OUTPUTS',out):
   with self.assertRaises(ValueError):launch.clear_outputs()
  self.assertTrue(out.is_symlink())
 def test_csv_rejects_previous_run(self):
  c.endpoint_once(self.config,'all_class',lambda *a,**kw:self.payload())
  with self.assertRaises(ValueError):q.query(self.root/'all_class.csv','SELECT * FROM data',run_id='new-run')
 def test_metadata_records_run_mode(self):
  self.config['mode']='live'
  self.assertEqual(c.metadata(self.config,'all_class','waiting',c.now())['run_mode'],'live')

if __name__=='__main__':unittest.main()
