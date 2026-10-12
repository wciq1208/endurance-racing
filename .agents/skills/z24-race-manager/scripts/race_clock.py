#!/usr/bin/env python3
"""Map the actual Beijing clock onto a 16:00-to-16:00 24-hour race cycle."""
import argparse
import csv
import datetime as dt
import sys
CST=dt.timezone(dt.timedelta(hours=8))

def race_clock(clock=None, finished=False):
    clock=clock or dt.datetime.now(CST)
    if clock.tzinfo is None:raise ValueError('clock must include timezone')
    clock=clock.astimezone(CST)
    anchor=clock.replace(hour=16,minute=0,second=0,microsecond=0)
    if clock<anchor:anchor-=dt.timedelta(days=1)
    elapsed=(clock-anchor).total_seconds()
    remaining=86400-elapsed
    if finished:elapsed,remaining=86400,0
    return {'now_beijing':clock.isoformat(timespec='seconds'),
            'mode':'finished' if finished else 'assumed_running_16_to_16',
            'elapsed_seconds':round(elapsed,3),'remaining_seconds':round(remaining,3),
            'elapsed_hours':round(elapsed/3600,6),'remaining_hours':round(remaining/3600,6)}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--finished',action='store_true',help='明确本场已结束，返回24小时/剩余0')
    args=parser.parse_args()
    writer=csv.writer(sys.stdout);result=race_clock(finished=args.finished)
    writer.writerow(result.keys());writer.writerow(result.values())
if __name__=='__main__':main()
