"""Versioned RFC4180 CSV: validate the full batch, then atomically replace a file."""
import csv
import datetime as dt
import io
import json
import os
from pathlib import Path
import tempfile
import time
import uuid
import portalocker
import re
import shutil
from .models import Run, Result, ControlMessage, Lap, LapAnalysis, WeatherFrame, Collection, Envelope

MODELS={'results':Result,'control_messages':ControlMessage,'laps':Lap,'pace':LapAnalysis,'weather':WeatherFrame}
LANE_DATA={'results':('results',),'control_message':('control_messages',),'laps':('laps','pace'),'weather':('weather',)}
IDENTITIES={'results':('result_id',),'control_messages':('message_id',),'laps':('result_id','lap_id'),'pace':('result_id',),'weather':('run_id','collected_at')}
NULL='\\N'


def atomic(path, data):
    """Same-directory rename; Windows may briefly hold a reader handle open."""
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='.'+path.name+'.',suffix='.tmp',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as handle:
            handle.write(data if isinstance(data,bytes) else data.encode('utf-8'))
            handle.flush();os.fsync(handle.fileno())
        for attempt in range(20):
            try:os.replace(name,path);break
            except PermissionError:
                if attempt==19:raise
                time.sleep(.05)
    finally:
        Path(name).unlink(missing_ok=True)


def run_from_config(config):
    s=config['selected']
    return Run(run_id=config['token'],skill_id=config.get('skill_id','z24-race-manager'),mode=config.get('mode','test'),
        team=config['team'],started_at=config.get('started_at',dt.datetime.now(dt.timezone.utc).isoformat()),
        station_id=str(s['ssid']),race_id=str(s['race_id']),round_id=str(s['round_id']),session_id=str(s['pid']),
        race_name=s.get('race_name',''),session_name=s.get('session_name',''),session_start=s.get('start_time'),
        session_status=str(s['session_status']) if s.get('session_status') is not None else None)


def initialize_run(folder,config):
    folder=Path(folder);run=run_from_config(config)
    path=folder/'run.json'
    if path.exists():
        existing=Run.model_validate_json(path.read_text(encoding='utf-8'))
        if existing.run_id!=run.run_id:raise ValueError('Run mismatch')
        return existing
    atomic(path,run.model_dump_json())
    return run


def encode(value):
    if value is None:return NULL
    if isinstance(value,bool):return str(value).lower()
    return str(value).replace('\\','\\\\')


def decode(value):
    return None if value==NULL else value.replace('\\\\','\\')


def serialize(envelope, rows):
    model=MODELS[envelope.dataset]
    if envelope.run.run_id!=envelope.collection.run_id:raise ValueError('Envelope run mismatch')
    if envelope.dataset not in LANE_DATA[envelope.collection.lane]:raise ValueError('Dataset/lane mismatch')
    values=[model.model_validate(r.model_dump() if hasattr(r,'model_dump') else r) for r in rows]
    if envelope.collection.status in ('waiting','error') and values:raise ValueError('Failed batches cannot contain data rows')
    if envelope.dataset=='weather' and any(r.run_id!=envelope.run.run_id or r.collected_at!=envelope.collection.collected_at for r in values):raise ValueError('Weather identity/timestamp mismatch')
    identities=[tuple(getattr(r,k) for k in IDENTITIES[envelope.dataset]) for r in values]
    if len(set(identities))!=len(identities):raise ValueError('Duplicate record identity')
    text=io.StringIO(newline='');writer=csv.writer(text)
    writer.writerow(['# collected_at',envelope.collection.collected_at.isoformat() if envelope.collection.collected_at else '',
                     'envelope',envelope.model_dump_json()])
    writer.writerow(list(model.model_fields))
    for row in values:writer.writerow([encode(v) for v in row.model_dump(mode='json').values()])
    return text.getvalue()


def parse_envelope(text):
    raw=json.loads(text)
    # Only the previous canonical CSV contract is upgraded, never raw API CSV.
    if raw.get('schema_version')==1:
        raw['schema_version']=2
        if raw.get('collection',{}).get('lane')=='all_class':raw['collection']['lane']='results'
    return Envelope.model_validate(raw)


def read_csv(path, run_id=None, dataset=None):
    path=Path(path)
    if path.name in ('laps.csv','pace.csv'):
        path=lap_batch_folder(path.parent)/path.name
    with path.open(encoding='utf-8',newline='') as handle:
        reader=csv.reader(handle,strict=True);first=next(reader)
        if len(first)!=4 or first[0]!='# collected_at' or first[2]!='envelope':raise ValueError('Invalid CSV metadata')
        envelope=parse_envelope(first[3])
        if run_id is not None and envelope.run.run_id!=run_id:raise ValueError('CSV run mismatch')
        if envelope.collection.run_id!=envelope.run.run_id:raise ValueError('Collection run mismatch')
        if dataset is not None and envelope.dataset!=dataset:raise ValueError('CSV dataset mismatch')
        if envelope.dataset not in LANE_DATA[envelope.collection.lane]:raise ValueError('Dataset/lane mismatch')
        stamp=envelope.collection.collected_at.isoformat() if envelope.collection.collected_at else ''
        if first[1]!=stamp:raise ValueError('CSV timestamp mismatch')
        model=MODELS[envelope.dataset];header=next(reader)
        if header!=list(model.model_fields):raise ValueError('CSV schema columns mismatch')
        rows=[]
        for line in reader:
            if len(line)!=len(header):raise ValueError('CSV row width mismatch')
            rows.append(model.model_validate(dict(zip(header,map(decode,line)))))
        identities=[tuple(getattr(r,k) for k in IDENTITIES[envelope.dataset]) for r in rows]
        if len(set(identities))!=len(identities):raise ValueError('Duplicate record identity')
        return envelope,rows


def publish(folder, collection, datasets):
    folder=Path(folder)
    run=Run.model_validate_json((folder/'run.json').read_text(encoding='utf-8'))
    if set(datasets)!=set(LANE_DATA[collection.lane]):raise ValueError('Publish a complete lane batch')
    snapshot=uuid.uuid4().hex
    # Validate and serialize ALL files before replacing any. Readers also check
    # snapshot_id when consuming the two-file laps/pace batch.
    prepared={name:serialize(Envelope(dataset=name,snapshot_id=snapshot,run=run,collection=collection),rows)
              for name,rows in datasets.items()}
    # A lock spans all replacements so two publishers cannot leave a mixed pair.
    with (folder/(collection.lane+'.publish.lock')).open('a') as lock:
        portalocker.lock(lock,portalocker.LOCK_EX)
        if collection.lane!='laps':
            for name,data in prepared.items():atomic(folder/(name+'.csv'),data)
            return
        # Immutable files first; the pointer is the only publication/commit step.
        batch=folder/'lap-batches'/snapshot
        batch.mkdir(parents=True)
        for name,data in prepared.items():atomic(batch/(name+'.csv'),data)
        previous=lap_batch_folder(folder)
        if previous!=folder and previous.is_dir():os.utime(previous,None)
        atomic(folder/'laps-active.json',json.dumps({'snapshot_id':snapshot}))
        # Failed/interrupted writes leave only unreferenced directories, pruned below.
        # Give in-flight readers time to finish their pinned snapshot (HTTP timeout 20s).
        # This is transaction retention, not a race history archive.
        for old in batch.parent.iterdir():
            if old.name!=snapshot and old.is_dir() and not old.is_symlink():
                try:
                    if time.time()-old.stat().st_mtime>300:shutil.rmtree(old)
                except OSError:pass


def failure(folder, collection):
    publish(folder,collection,{name:[] for name in LANE_DATA[collection.lane]})


def freshness(envelope, now=None):
    now=now or dt.datetime.now(dt.timezone.utc)
    c=envelope.collection
    age=(now-c.collected_at).total_seconds() if c.collected_at else None
    clock_valid=age is not None and age>=-5
    if age is not None and c.lane=='laps':
        attempt_age=(now-c.attempted_at).total_seconds()
        clock_valid=clock_valid and attempt_age>=-5
        age=max(age,attempt_age)
    return dict(lane=c.lane,status=c.status,attempted_at=c.attempted_at.isoformat(),
        collected_at=c.collected_at.isoformat() if c.collected_at else None,error=c.error,
        age_seconds=age,fresh=c.status=='ok' and clock_valid and age is not None and age<=(240 if c.lane=='weather' else 120))


def read_active(path, run_id):
    state=json.loads(Path(path).read_text(encoding='utf-8'))
    if state.get('token')!=run_id:raise ValueError('Not the active run')
    return state


def pace_fresh(row, mode, now=None):
    now=now or dt.datetime.now(dt.timezone.utc)
    def recent(stamp):
        age=(now-stamp).total_seconds()
        return -5<=age<=120
    return row.status=='ok' and recent(row.received_at) and (mode=='test' or recent(row.analysis_at))


def lap_batch_folder(folder):
    folder=Path(folder)
    pointer=folder/'laps-active.json'
    try:state=json.loads(pointer.read_text(encoding='utf-8'))
    except FileNotFoundError:return folder  # Previous canonical runs remain readable.
    snapshot=state.get('snapshot_id')
    if not isinstance(snapshot,str) or not re.fullmatch('[a-f0-9]{32}',snapshot):
        raise ValueError('Invalid lap batch pointer')
    return folder/'lap-batches'/snapshot


def read_lap_batch(folder,run_id=None):
    # Pin once; do not re-read the mutable pointer between the two files.
    batch=lap_batch_folder(folder)
    laps=read_csv(batch/'laps.csv',run_id,'laps')
    pace=read_csv(batch/'pace.csv',run_id,'pace')
    if laps[0].snapshot_id!=pace[0].snapshot_id:
        raise ValueError('Lap batch changed; retry both files')
    if batch.parent.name=='lap-batches' and batch.name!=laps[0].snapshot_id:
        raise ValueError('Lap pointer/snapshot mismatch')
    return {'laps':laps,'pace':pace}
