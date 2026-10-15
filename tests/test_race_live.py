"""Upstream adapter -> Pydantic -> atomic canonical CSV, without a DB or API."""
import concurrent.futures
import csv
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'.agents/skills/z24-race-manager/scripts'))
import race_live_common as c
from race_data.csv_io import publish,read_csv,freshness,atomic,lap_batch_folder
from race_data.models import Collection
from race_csv_read import load

class LiveTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve()
  self.config={'selected':{'ssid':262,'race_id':1,'round_id':2,'pid':3,'session_status':3},'team':'A','token':'unique-token','output':str(self.root),'interval':60}
  c.data_folder(self.config)
 def tearDown(self):self.tmp.cleanup()
 def payload(self):
  return {'flag':1,'round':{'id':3,'ri_end':'2025/12/21 16:00:00'},'items':[{'id':1,'carNo':'025','carTeam':'A','laps':100,'bestTm':61234,'gap':1234,'diff':-8}]}
 def collect(self,lane='all_class',payload=None):c.endpoint_once(self.config,lane,lambda *a,**kw:payload or self.payload())
 def read(self,dataset='results'):return read_csv(self.root/(dataset+'.csv'),'unique-token',dataset)
 def test_canonical_units_identifiers_and_nulls(self):
  self.collect();meta,rows=self.read();r=rows[0]
  self.assertEqual(r.car_number,'025');self.assertEqual(r.best_lap_seconds,61.234);self.assertEqual(r.gap_seconds,1.234)
  self.assertEqual(r.leader_gap_laps,8);self.assertIsNone(r.leader_gap_seconds);self.assertIsNone(r.pit_stops)
  self.assertTrue(freshness(meta)['fresh']);self.assertFalse((self.root/'all_class.csv').exists())
 def test_multiline_announcement_and_escape_roundtrip(self):
  body='更正,撤销\n"25号"原处罚\\N\\\\path'
  self.collect('control_message',dict(flag=1,round=dict(id=3),items=[dict(id=5,index=2,cont=body,c_time='')]))
  _,rows=self.read('control_messages');self.assertEqual(rows[0].body,body);self.assertIsNone(rows[0].published_at_source)
  # Literal sentinel remains text, optional None and empty text are distinct.
  status=Collection(run_id='unique-token',lane='control_message',status='ok',attempted_at=c.now(),collected_at=c.now())
  publish(self.root,status,{'control_messages':[dict(message_id='x',body='',published_at_source='\\N')]})
  row=self.read('control_messages')[1][0];self.assertEqual(row.body,'');self.assertEqual(row.published_at_source,'\\N')
 def test_invalid_batch_never_replaces_success(self):
  self.collect();before=(self.root/'results.csv').read_bytes()
  for bad in [float('nan'),-1,'not-numeric']:
   payload=self.payload();payload['items'].append(dict(payload['items'][0],id=2,bestTm=bad))
   with self.assertRaises(ValueError):self.collect(payload=payload)
   self.assertEqual((self.root/'results.csv').read_bytes(),before)
 def test_failure_publishes_explicit_empty_error(self):
  self.collect();c.failure(self.config,'all_class','offline')
  meta,rows=self.read();self.assertEqual(rows,[]);self.assertFalse(freshness(meta)['fresh'])
  self.assertEqual(meta.collection.status,'error');self.assertIsNone(meta.collection.collected_at)
 def test_wrong_session_never_published(self):
  payload=self.payload();payload['round']['id']=4
  with self.assertRaises(ValueError):self.collect(payload=payload)
  self.assertFalse((self.root/'results.csv').exists())
 def test_duplicate_records_rejected(self):
  self.collect();meta,rows=self.read();before=(self.root/'results.csv').read_bytes()
  with self.assertRaises(ValueError):publish(self.root,meta.collection,{'results':rows*2})
  self.assertEqual((self.root/'results.csv').read_bytes(),before)
 def test_models_reject_inconsistent_units_and_collection_time(self):
  from race_data.models import Result
  with self.assertRaises(ValueError):Result(result_id='1',car_number='01',team_name='A',gap_seconds=1,gap_laps=2)
  with self.assertRaises(ValueError):Collection(run_id='x',lane='results',status='ok',attempted_at=c.now())
  with self.assertRaises(ValueError):Collection(run_id='x',lane='results',status='error',attempted_at=c.now(),collected_at=c.now())
 def test_read_rejects_wrong_run_version_or_header(self):
  self.collect()
  with self.assertRaises(ValueError):read_csv(self.root/'results.csv','wrong')
  text=(self.root/'results.csv').read_text()
  for value in [text.replace('schema_version"":2','schema_version"":3'),text.replace('car_number','carNo')]:
   atomic(self.root/'bad.csv',value)
   with self.assertRaises(ValueError):read_csv(self.root/'bad.csv')
 def test_previous_canonical_csv_reads_as_results_lane(self):
  self.collect();path=self.root/'results.csv'
  raw=path.read_text().replace('schema_version"":2','schema_version"":1').replace('lane"":""results','lane"":""all_class')
  atomic(path,raw)
  meta,rows=self.read();self.assertEqual(meta.collection.lane,'results');self.assertEqual(len(rows),1)
 def test_atomic_readers_only_see_complete_snapshots(self):
  self.collect()
  def writer():
   for _ in range(20):self.collect()
  with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
   future=pool.submit(writer)
   for _ in range(100):self.assertEqual(len(self.read()[1]),1)
   future.result()
  self.assertEqual(list(self.root.glob('*.tmp')),[])
 def test_replace_failure_keeps_old_file_and_cleans_temp(self):
  self.collect();path=self.root/'results.csv';before=path.read_bytes()
  with patch('race_data.csv_io.os.replace',side_effect=OSError('disk failure')):
   with self.assertRaises(OSError):atomic(path,'incomplete')
  self.assertEqual(path.read_bytes(),before);self.assertFalse(list(self.root.glob('*.tmp')))
 def test_windows_reader_handle_retry(self):
  import os
  original=os.replace
  with patch('race_data.csv_io.os.replace',side_effect=[PermissionError('reader'),None]) as replace,patch('race_data.csv_io.time.sleep'):
   atomic(self.root/'probe','ok');self.assertEqual(replace.call_count,2)
 def test_old_or_future_data_not_fresh(self):
  self.collect();meta,_=self.read()
  for stamp in ['2020-01-01T00:00:00+08:00','2099-01-01T00:00:00+08:00']:
   meta.collection=meta.collection.model_copy(update={'collected_at':__import__('datetime').datetime.fromisoformat(stamp)})
   self.assertFalse(freshness(meta)['fresh'])
 def test_lap_pair_batch_mismatch_rejected(self):
  status=Collection(run_id='unique-token',lane='laps',status='ok',attempted_at=c.now(),collected_at=c.now())
  publish(self.root,status,{'laps':[],'pace':[]});old=(lap_batch_folder(self.root)/'laps.csv').read_bytes()
  publish(self.root,status,{'laps':[],'pace':[]});atomic(lap_batch_folder(self.root)/'laps.csv',old)
  active=self.root/'active.json';active.write_text(json.dumps(dict(token='unique-token',data_output=str(self.root))))
  with self.assertRaises(ValueError):load(active,'unique-token','pace')
 def test_weather_failure_is_independent(self):
  self.collect();c.failure(self.config,'weather','timeout')
  from PIL import Image
  with Image.open(self.root/'radar.png') as image:self.assertEqual(image.info['status'],'error')
  self.assertEqual(len(self.read()[1]),1)
 def test_cleanup_scoped_and_refuses_symlinks(self):
  import race_live
  owned=self.root/'owned';public=self.root/'public';other=self.root/'other'
  for folder in (owned,public,other):folder.mkdir();(folder/'keep').write_text('x')
  with patch.object(race_live,'OUTPUTS',owned),patch.object(race_live,'PUBLIC',public):race_live.clear_current_outputs()
  self.assertTrue((other/'keep').exists());self.assertEqual(list(owned.iterdir()),[])
  link=self.root/'link'
  try:link.symlink_to(other,target_is_directory=True)
  except OSError:self.skipTest('Symlinks require Windows Developer Mode')
  with patch.object(race_live,'OUTPUTS',owned),patch.object(race_live,'PUBLIC',link):
   with self.assertRaises(ValueError):race_live.clear_current_outputs()
  self.assertTrue((other/'keep').exists())
 def test_worker_survives_errors(self):
  path=self.root/'config.json';path.write_text(json.dumps(self.config))
  with patch.object(sys,'argv',['worker.py','--config',str(path),'--token','unique-token']),patch.object(c.subprocess,'run',side_effect=RuntimeError('offline')) as run,patch.object(c.time,'sleep',side_effect=[None,KeyboardInterrupt]),patch.object(c.traceback,'print_exc'):
   with self.assertRaises(KeyboardInterrupt):c.worker_main('all_class',lambda config:None)
   self.assertEqual(run.call_count,2)
  self.assertEqual(self.read()[0].collection.status,'error')

 def test_concurrent_lane_publish_is_serialized(self):
  import threading
  import race_data.csv_io as io
  c=Collection(run_id='unique-token',lane='laps',status='ok',attempted_at=__import__('race_live_common').now(),collected_at=__import__('race_live_common').now())
  first_written=threading.Event();release=threading.Event();second_write=threading.Event()
  original=io.atomic
  def controlled(path,data):
   if threading.current_thread().name=='second':second_write.set()
   original(path,data)
   if threading.current_thread().name=='first' and Path(path).name=='laps.csv':
    first_written.set()
    if not release.wait(5):raise RuntimeError('release timed out')
  errors=[]
  def writer():
   try:io.publish(self.root,c,{'laps':[],'pace':[]})
   except Exception as e:errors.append(e)
  with patch.object(io,'atomic',side_effect=controlled):
   first=threading.Thread(target=writer,name='first');second=threading.Thread(target=writer,name='second')
   first.start();self.assertTrue(first_written.wait(5));second.start()
   try:self.assertFalse(second_write.wait(.2))
   finally:release.set();first.join(5);second.join(5)
  self.assertFalse(first.is_alive() or second.is_alive());self.assertEqual(errors,[])
  self.assertEqual(io.read_csv(self.root/'laps.csv')[0].snapshot_id,io.read_csv(self.root/'pace.csv')[0].snapshot_id)
 def test_slow_lap_batch_and_old_analysis_are_not_fresh(self):
  import datetime as dt
  from race_data.csv_io import freshness,pace_fresh
  from race_data.models import Envelope,LapAnalysis,Run
  stamp=dt.datetime.now(dt.timezone.utc);old=stamp-dt.timedelta(seconds=190)
  run=Run.model_validate_json((self.root/'run.json').read_text())
  c=Collection(run_id=run.run_id,lane='laps',status='ok',attempted_at=old,collected_at=stamp)
  envelope=Envelope(dataset='pace',snapshot_id='x',run=run,collection=c)
  self.assertFalse(freshness(envelope,stamp)['fresh'])
  c.attempted_at=stamp;c.collected_at=stamp+dt.timedelta(seconds=60)
  self.assertFalse(freshness(envelope,stamp)['fresh'])
  c.collected_at=stamp;c.attempted_at=stamp+dt.timedelta(seconds=60)
  self.assertFalse(freshness(envelope,stamp)['fresh'])
  row=LapAnalysis(result_id='1',analysis_at=old,received_at=stamp,car_number='1',team_name='A',status='ok')
  self.assertFalse(pace_fresh(row,'live',stamp));self.assertTrue(pace_fresh(row,'test',stamp))
  row.received_at=old;self.assertFalse(pace_fresh(row,'test',stamp))

 def test_lap_publication_failures_keep_previous_complete_batch(self):
  import race_data.csv_io as io
  status=Collection(run_id='unique-token',lane='laps',status='ok',attempted_at=c.now(),collected_at=c.now())
  io.publish(self.root,status,{'laps':[],'pace':[]})
  active=self.root/'active.json';active.write_text(json.dumps(dict(token='unique-token',data_output=str(self.root))))
  before=(self.root/'laps-active.json').read_bytes()
  original=io.atomic
  for fail_name in ('laps.csv','pace.csv','laps-active.json'):
   def failing(path,data):
    if Path(path).name==fail_name:raise OSError('disk write failed')
    original(path,data)
   with patch.object(io,'atomic',side_effect=failing):
    with self.assertRaises(OSError):io.publish(self.root,status,{'laps':[],'pace':[]})
   self.assertEqual((self.root/'laps-active.json').read_bytes(),before)
   self.assertEqual(io.read_lap_batch(self.root)['laps'][0].snapshot_id,io.read_lap_batch(self.root)['pace'][0].snapshot_id)
   load(active,'unique-token','pace')
  io.publish(self.root,status,{'laps':[],'pace':[]})
  self.assertNotEqual((self.root/'laps-active.json').read_bytes(),before)
 def test_killed_lap_publisher_keeps_previous_complete_batch(self):
  import subprocess
  import race_data.csv_io as io
  status=Collection(run_id='unique-token',lane='laps',status='ok',attempted_at=c.now(),collected_at=c.now())
  io.publish(self.root,status,{'laps':[],'pace':[]})
  before=(self.root/'laps-active.json').read_bytes()
  code="""import os,sys,datetime as dt
from pathlib import Path
import race_data.csv_io as io
from race_data.models import Collection
original=io.atomic
def killed(path,data):
 if Path(path).name=='pace.csv':os._exit(23)
 original(path,data)
io.atomic=killed
stamp=dt.datetime.now(dt.timezone.utc)
c=Collection(run_id='unique-token',lane='laps',status='ok',attempted_at=stamp,collected_at=stamp)
io.publish(sys.argv[1],c,{'laps':[],'pace':[]})
"""
  child=subprocess.run([sys.executable,'-c',code,str(self.root)],cwd=ROOT,timeout=10)
  self.assertEqual(child.returncode,23);self.assertEqual((self.root/'laps-active.json').read_bytes(),before)
  self.assertEqual(io.read_lap_batch(self.root)['laps'][0].snapshot_id,io.read_lap_batch(self.root)['pace'][0].snapshot_id)
  io.publish(self.root,status,{'laps':[],'pace':[]})  # Crash released the publication lock.
 def test_lap_reader_pins_pointer_once(self):
  import race_data.csv_io as io
  status=Collection(run_id='unique-token',lane='laps',status='ok',attempted_at=c.now(),collected_at=c.now())
  io.publish(self.root,status,{'laps':[],'pace':[]});old=io.read_lap_batch(self.root)['pace'][0].snapshot_id
  original=io.read_csv
  def switching(path,*args):
   value=original(path,*args)
   if Path(path).name=='laps.csv':io.publish(self.root,status,{'laps':[],'pace':[]})
   return value
  with patch.object(io,'read_csv',side_effect=switching):pair=io.read_lap_batch(self.root)
  self.assertEqual(pair['laps'][0].snapshot_id,old);self.assertEqual(pair['pace'][0].snapshot_id,old)

 def test_retention_starts_when_batch_is_superseded(self):
  import os,time
  import race_data.csv_io as io
  status=Collection(run_id='unique-token',lane='laps',status='ok',attempted_at=c.now(),collected_at=c.now())
  io.publish(self.root,status,{'laps':[],'pace':[]});previous=io.lap_batch_folder(self.root)
  os.utime(previous,(time.time()-600,time.time()-600))
  orphan=previous.parent/('e'*32);orphan.mkdir();os.utime(orphan,(time.time()-600,time.time()-600))
  io.publish(self.root,status,{'laps':[],'pace':[]})
  self.assertTrue(previous.exists());self.assertFalse(orphan.exists())
  self.assertEqual(io.read_lap_batch(previous)['laps'][0].snapshot_id,previous.name)
