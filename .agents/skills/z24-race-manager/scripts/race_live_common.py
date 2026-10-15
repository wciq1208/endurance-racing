"""Shared I/O and persistent polling for independent race lanes with cross-platform file locks."""
import argparse
import datetime as dt
import portalocker
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

SKILL_SCRIPTS = Path(__file__).resolve().parent
ROOT = SKILL_SCRIPTS.parents[3]
WEATHER_SCRIPTS = ROOT/'scripts'
sys.path.insert(0,str(WEATHER_SCRIPTS))
sys.path.insert(0,str(ROOT))
CST = dt.timezone(dt.timedelta(hours=8))
LANES = ('weather', 'all_class', 'control_message')
FILES = {'weather': 'radar.png'}

def now():
    return dt.datetime.now(CST).isoformat(timespec='milliseconds')

def atomic(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name+f'.{os.getpid()}.tmp')
    if isinstance(data, bytes): tmp.write_bytes(data)
    else: tmp.write_text(data, encoding='utf-8')
    tmp.replace(path)

def metadata(config, lane, status, attempted_at, collected_at='', error='', **extra):
    d = config['selected']
    return dict(collected_at=collected_at, attempted_at=attempted_at, status=status,
                run_id=config['token'], run_mode=config.get('mode','test'), endpoint=lane, team=config['team'],
                ssid=d['ssid'], race_id=d['race_id'], round_id=d['round_id'], pid=d['pid'],
                session_status=d.get('session_status',''), race_name=d.get('race_name',''),
                session_start=d.get('start_time',''), error=str(error)[:600], **extra)

def data_folder(config):
    from race_data.csv_io import initialize_run
    path=Path(config.get('data_output',config['output']))
    initialize_run(path,config)
    return path


def failure(config, lane, error, status='error'):
    from race_data.csv_io import failure as publish_failure
    from race_adapter import collection
    meta=metadata(config,lane,status,now(),error=error)
    folder=data_folder(config)
    publish_failure(folder,collection(meta))
    if lane=='weather':
        from race_weather import failure_image
        failure_image(folder/'radar.png',meta,config.get('weather',{}).get('location','赛场'),error)


def endpoint_once(config, lane, fetch=None):
    from myracing_read import read
    from race_validation import validate, ENDPOINTS
    fetch = fetch or read
    started=now();selected=config['selected']
    params={'ssid':selected['ssid'],'userId':0,'pid':selected['pid']}
    if lane=='all_class':params.update(isTest=1,group='')
    payload=fetch(ENDPOINTS[lane],**params)
    validate(payload,selected['pid'])
    received=now();round_info=payload['round']
    meta=metadata(config,lane,'ok',started,received,
                  round_end=round_info.get('ri_end',''),round_start=round_info.get('ri_start',''),
                  round_flag=round_info.get('ri_flag',''),row_count=len(payload['items']))
    from race_data.csv_io import publish
    from race_adapter import collection, result, message
    convert=result if lane=='all_class' else message
    rows=[convert(row) for row in payload['items']]
    publish(data_folder(config),collection(meta),{'results' if lane=='all_class' else 'control_messages':rows})

def worker_main(lane, once):
    p=argparse.ArgumentParser(description='Independent persistent '+lane+' collector')
    p.add_argument('--config',type=Path,required=True);p.add_argument('--token',required=True)
    p.add_argument('--once',action='store_true')
    a=p.parse_args();config=json.loads(a.config.read_text(encoding='utf-8'))
    if config['token']!=a.token:raise ValueError('run token mismatch')
    if a.once:
        # A surviving one-shot from a crashed worker cannot overlap its replacement.
        with (Path(config['output'])/(lane+'.lock')).open('a') as lock:
            portalocker.lock(lock,portalocker.LOCK_EX)
            once(config)
        return
    interval=float(config['interval'])
    while True:
        tick=time.monotonic()
        try:
            subprocess.run([sys.executable,str(Path(sys.argv[0]).resolve()),'--config',str(a.config.resolve()),
                            '--token',a.token,'--once'],check=True,timeout=90 if lane=='weather' else 25)
        except Exception as exc:
            traceback.print_exc()
            try:failure(config,lane,exc)
            except Exception:traceback.print_exc()
        # No overlapping requests/catch-up storm after a slow poll.
        time.sleep(max(0,interval-(time.monotonic()-tick)))
