#!/usr/bin/env python3
"""Validate the canonical CSV, current run and freshness before Python analysis."""
import argparse
import json
from pathlib import Path
from race_live_common import ROOT,now
from race_data.csv_io import read_active,read_csv,read_lap_batch,freshness,pace_fresh,MODELS


def load(active_path,run_id,dataset):
    state=read_active(active_path,run_id)
    folder=Path(state['data_output'])
    if dataset in ('laps','pace'):
        envelope,rows=read_lap_batch(folder,run_id)[dataset]
    else:envelope,rows=read_csv(folder/(dataset+'.csv'),run_id,dataset)
    read_active(active_path,run_id)
    return envelope,rows


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--active',type=Path,default=ROOT/'.runtime/z24-race-manager/active.json')
    p.add_argument('--run-id',required=True);p.add_argument('--dataset',choices=MODELS,required=True)
    p.add_argument('--limit',type=int,default=40)
    a=p.parse_args()
    if not 0<=a.limit<=10000:p.error('limit must be 0..10000')
    envelope,rows=load(a.active,a.run_id,a.dataset)
    print(json.dumps(dict(query_now=now(),metadata=envelope.model_dump(mode='json'),freshness=freshness(envelope),
        row_count=len(rows),pace_freshness={r.result_id:pace_fresh(r,envelope.run.mode) for r in rows} if a.dataset=='pace' else None,rows=[r.model_dump(mode='json') for r in rows[:a.limit]]),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
