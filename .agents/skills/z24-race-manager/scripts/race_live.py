#!/usr/bin/env python3
"""Start/replace this project's detached, supervised three-lane race collectors."""
import argparse
import portalocker
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback
import uuid
from race_process import detached_options, owned_processes, stop_owned
from race_live_common import ROOT, SKILL_SCRIPTS, WEATHER_SCRIPTS, LANES, atomic, failure, now

SKILL_ID='z24-race-manager'
VENUE_WEATHER=dict(lat=27.8206,lon=113.062648,station='az9731',location='株洲国际卡丁车场')
STATE=ROOT/'.runtime'/SKILL_ID
OUTPUTS=STATE/'outputs'
SCRIPTS={'weather':WEATHER_SCRIPTS/'race_weather.py','all_class':SKILL_SCRIPTS/'race_all_class.py','control_message':SKILL_SCRIPTS/'race_control_message.py'}

def clear_outputs():
    # Never follow a symlink into an unrelated directory. launch.lock stays outside.
    if STATE.parent.is_symlink() or STATE.is_symlink() or OUTPUTS.is_symlink():
        raise ValueError('受管运行目录不能是符号链接')
    if OUTPUTS.exists():shutil.rmtree(OUTPUTS)
    OUTPUTS.mkdir(parents=True)


def managed_scripts():
    return [*SCRIPTS.values(), SKILL_SCRIPTS/'race_live.py',
            *(ROOT/'tools'/name for name in ('race_live.py','race_weather.py','race_all_class.py','race_control_message.py'))]


def owned_group(state):
    return bool(owned_processes(state, managed_scripts()))


def stop_group(state):
    return stop_owned(state, managed_scripts())


def worker_command(lane,config_path,config):
    if lane=='weather':
        w=config['weather']
        return [sys.executable,str(SCRIPTS[lane]),'--output',config['output'],
                '--token',config['token'],'--mode',config['mode'],'--interval',str(config['interval']),
                '--lat',str(w['lat']),'--lon',str(w['lon']),'--station',w['station'],'--location',w['location']]
    return [sys.executable,str(SCRIPTS[lane]),'--config',str(config_path),'--token',config['token']]


def supervise(config_path, token):
    config=json.loads(config_path.read_text(encoding='utf-8'))
    if config['token']!=token:raise ValueError('token mismatch')
    out=Path(config['output']);children={};retry={};logs={}
    while True:
        for lane in LANES:
            try:
                child=children.get(lane)
                if child is not None and child.poll() is None:continue
                if child is not None:
                    children[lane]=None;retry[lane]=time.monotonic()+config['interval']
                    failure(config,lane,'worker exited; supervisor will restart')
                if time.monotonic()<retry.get(lane,0):continue
                if lane not in logs:logs[lane]=(out/'logs'/f'{lane}.log').open('a',encoding='utf-8')
                child=subprocess.Popen(worker_command(lane,config_path,config),stdout=logs[lane],stderr=subprocess.STDOUT)
                children[lane]=child
                atomic(out/'workers.json',json.dumps({k:v.pid if v else None for k,v in children.items()}))
            except Exception:
                traceback.print_exc();retry[lane]=time.monotonic()+config['interval']
        time.sleep(1)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['start','stop','status','doctor','supervise'])
    p.add_argument('--mode',choices=['live','test'],default='live')
    p.add_argument('--team');p.add_argument('--year',type=int,default=2026)
    p.add_argument('--discovery',type=Path);p.add_argument('--interval',type=float,default=30)
    p.add_argument('--config',type=Path);p.add_argument('--token')
    a=p.parse_args()
    if a.action=='doctor':
        from race_doctor import report
        result=report();print(json.dumps(result,ensure_ascii=False,indent=2))
        if not result['ready']:raise SystemExit(1)
        return
    if a.action=='supervise':
        supervise(a.config.resolve(),a.token);return
    if STATE.parent.is_symlink() or STATE.is_symlink():p.error('运行目录不能是符号链接')
    STATE.mkdir(parents=True,exist_ok=True)
    with (STATE/'launch.lock').open('a',encoding='utf-8') as lock:
        portalocker.lock(lock,portalocker.LOCK_EX)
        active=STATE/'active.json'
        old=json.loads(active.read_text(encoding='utf-8')) if active.exists() else None
        if a.action=='status':
            print(json.dumps(dict(now=now(),running=owned_group(old),active=old),ensure_ascii=False,indent=2));return
        if a.action=='stop':
            print('stopped' if stop_group(old) else 'not running');active.unlink(missing_ok=True);return
        if not a.team or not a.team.strip():p.error('启动必须指定 --team 车队完整名称')
        if not 5<=a.interval<=3600:p.error('interval须为5..3600秒，默认30秒')
        from race_doctor import report
        health=report()
        if not health['ready']:p.error('环境检查失败：'+json.dumps(health,ensure_ascii=False))
        for warning in health['warnings']:print(warning,file=sys.stderr)
        # Cleanup is scoped to this skill, regardless of the previous race/year.
        stop_group(old)
        if owned_group(old):p.error('旧进程未退出，拒绝清理产出')
        active.unlink(missing_ok=True)
        # Read explicit configuration before clearing any generated outputs.
        try:
            supplied=json.loads(a.discovery.read_text(encoding='utf-8')) if a.discovery else None
        finally:
            clear_outputs()
        if a.discovery:
            d=supplied
        else:
            from myracing_discover import discover
            d=discover(262,a.year)
        if d.get('status')!='ready':p.error('赛事未唯一就绪：'+json.dumps(d,ensure_ascii=False))
        selected=d['selected']
        if selected.get('ssid')!=262 or any(int(selected[k])<=0 for k in ('ssid','race_id','round_id','pid')):
            p.error('需要湖南国际卡丁车场有效赛事ID')
        if a.mode=='live' and str(selected.get('session_status'))=='3':
            p.error('该场次已结束；历史测试请显式使用 --mode test')
        token=uuid.uuid4().hex
        out=OUTPUTS/token
        (out/'logs').mkdir(parents=True)
        config={'skill_id':SKILL_ID,'weather':dict(VENUE_WEATHER),'mode':a.mode,'token':token,'team':a.team.strip(),'selected':selected,'interval':a.interval,'output':str(out),'started_at':now()}
        config_path=out/'config.json';atomic(config_path,json.dumps(config,ensure_ascii=False,indent=2))
        for lane in LANES:
            try:failure(config,lane,'waiting for first poll',status='waiting')
            except Exception:traceback.print_exc()
        with (out/'logs/supervisor.log').open('a',encoding='utf-8') as log:
            child=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'supervise',
                  '--config',str(config_path),'--token',token],stdin=subprocess.DEVNULL,
                  stdout=log,stderr=subprocess.STDOUT,close_fds=True,
                  env={**os.environ,'PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8'},**detached_options())
        state=dict(pid=child.pid,platform=sys.platform,token=token,output=str(out),config=str(config_path),started_at=now(),team=config['team'])
        atomic(active,json.dumps(state,ensure_ascii=False,indent=2))
        print(json.dumps(state,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
