#!/usr/bin/env python3
"""Guest lap supplementation: actual crossings and code-computed pace, published as canonical CSV."""
import argparse
import concurrent.futures
import datetime as dt
import math
from pathlib import Path
import statistics
from myracing_read import read
from race_live_common import CST, ROOT, now
import json
from race_data.csv_io import read_csv, read_active, freshness, publish
from race_data.models import Lap, Collection
from race_clock import race_clock


def crossing(item):
    coarse=dt.datetime.strptime(item['ri_time_of_day'],'%Y/%m/%d %H:%M:%S').replace(tzinfo=CST)
    precise=item.get('timeOfDay')
    if precise:
        tod=dt.time.fromisoformat(precise)
        candidate=dt.datetime.combine(coarse.date(),tod,tzinfo=CST)
        if abs((candidate-coarse).total_seconds())<1:return candidate
        raise ValueError('精细过线时间与日期时间冲突')
    return coarse


def summarize(items, at, pit_cost=180):
    if at.tzinfo is None:raise ValueError('at requires timezone')
    records=[]
    for item in items:
        t=crossing(item)
        seconds=float(item['lapTm'])/1000
        if not math.isfinite(seconds) or seconds<=0:raise ValueError('invalid lap duration')
        if t<=at:records.append((t,item,seconds))
    records.sort(key=lambda r:r[0])
    if not records:return [],dict(status='no_laps_before_cutoff')
    window=records[-10:];median=statistics.median(r[2] for r in window)
    clean=[r[2] for r in window if .5*median<=r[2]<=1.5*median]
    pace=statistics.median(clean)
    spread=statistics.median(abs(x-pace) for x in clean)
    age=(at-records[-1][0]).total_seconds()
    previous=records[-20:-10]
    prev=statistics.median(r[2] for r in previous) if len(previous)>=5 else None
    summary=dict(status='ok',laps_at_cutoff=records[-1][1]['laps'],last_crossing_at=records[-1][0].isoformat(),
                 last_lap_seconds=records[-1][2],crossing_age_seconds=round(age,3),
                 pace_median_seconds=round(pace,3),pace_mad_seconds=round(spread,3),pace_samples=len(clean),
                 excluded_recent_laps=len(window)-len(clean),
                 previous10_median_seconds=round(prev,3) if prev else None,
                 pace_change_seconds=round(pace-prev,3) if prev else None,
                 assumed_pit_loss_seconds=pit_cost,pit_loss_equivalent_laps=round(pit_cost/pace,3),
                 phase_estimate_usable=len(clean)>=5 and 0<=age<=1.5*pace and records[-1][2]<=1.5*pace)
    return records,summary


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--active',type=Path,default=ROOT/'.runtime/z24-race-manager/active.json')
    p.add_argument('--run-id',required=True);p.add_argument('--team',required=True)
    p.add_argument('--cars',default='',help='额外车号，以逗号分隔');p.add_argument('--all-cars',action='store_true')
    when=p.add_mutually_exclusive_group();when.add_argument('--at',help='历史截止时刻，ISO含时区');when.add_argument('--replay-cycle',action='store_true')
    p.add_argument('--pit-cost',type=float,default=180,help='用户假定净损失秒数，仅作情景计算')
    a=p.parse_args()
    if not math.isfinite(a.pit_cost) or a.pit_cost<=0:p.error('pit-cost must be positive finite')
    active=read_active(a.active,a.run_id)
    envelope,results=read_csv(Path(active['data_output'])/'results.csv',a.run_id,'results')
    if not freshness(envelope)['fresh']:p.error('成绩输入失败或超过120秒')
    meta=json.loads(envelope.collection.metadata_json)
    teams=[dict(carNo=r.car_number,carTeam=r.team_name,nicname=r.driver_name or '',id=r.result_id) for r in results]
    targets=[t for t in teams if a.team.strip() in {t.get('carTeam','').strip(),t.get('nicname','').strip()}]
    if len(targets)!=1:p.error('目标车队必须唯一匹配')
    clock=dt.datetime.now(CST)
    at=dt.datetime.fromisoformat(a.at) if a.at else clock
    mode='historical_cutoff' if a.at else 'live_time'
    if a.replay_cycle:
        start=dt.datetime.strptime(meta.get('round_start') or meta['session_start'],'%Y/%m/%d %H:%M:%S').replace(tzinfo=CST)
        at=start+dt.timedelta(seconds=race_clock(clock)['elapsed_seconds']);mode='historical_laps_at_mapped_clock'
    if at.tzinfo is None:p.error('at必须含时区')
    wanted=set(a.cars.split(','))|{targets[0]['carNo']}
    selected=[t for t in teams if a.all_cars or t['carNo'] in wanted]
    def fetch(team):
        received=now()
        try:
            payload=read('get-race-result-item',ssid=int(meta['ssid']),userId=0,pid=int(team['id']))
            received=now()
            if str(payload.get('flag'))!='1' or not isinstance(payload.get('items'),list):raise ValueError('逐圈接口业务失败')
            records,summary=summarize(payload['items'],at,a.pit_cost)
            return team,received,records,summary
        except Exception as e:return team,received,[],dict(status='error',error=str(e))
    all_laps=[];summaries=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for team,received,records,summary in pool.map(fetch,selected):
            prefix=dict(carNo=team['carNo'],carTeam=team.get('carTeam') or team.get('nicname'),result_id=team['id'],received_at=received,analysis_at=at.isoformat())
            summaries.append(dict(prefix,**summary))
            all_laps.extend(dict(prefix,lap_id=item['id'],laps=item['laps'],crossing_at=t.isoformat(),lap_seconds=seconds) for t,item,seconds in records)
    errors=sum(s['status']=='error' for s in summaries)
    collected=now()
    status=Collection(run_id=a.run_id,lane='laps',status='partial' if errors else 'ok',
        attempted_at=clock.isoformat(),collected_at=collected,
        metadata_json=json.dumps(dict(mode=mode,analysis_at=at.isoformat(),queried_cars=len(selected),total_cars=len(teams),failed_cars=errors)))
    rows=[Lap(result_id=str(r['result_id']),car_number=r['carNo'],team_name=r['carTeam'],
        lap_id=str(r['lap_id']),lap_number=r['laps'],crossing_at=r['crossing_at'],lap_seconds=r['lap_seconds'],received_at=r['received_at']) for r in all_laps]
    analyses=[]
    for summary in summaries:
        values={k:v for k,v in summary.items() if k not in {'carNo','carTeam'}}
        values.update(car_number=summary['carNo'],team_name=summary['carTeam'])
        analyses.append(values)
    read_active(a.active,a.run_id)
    publish(active['data_output'],status,{'laps':rows,'pace':analyses})
    for s in summaries:print(s)

if __name__=='__main__':main()
