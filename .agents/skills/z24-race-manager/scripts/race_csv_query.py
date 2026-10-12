#!/usr/bin/env python3
"""Query one collected CSV using read-only SQLite SQL; calculations execute in code."""
import argparse
import csv
import datetime as dt
import io
import sqlite3
from pathlib import Path
from race_live_common import read_csv, now

# Preserve identity-like columns as text; numeric timing fields use numeric affinity.
NUMERIC={'pos','pic','laps','bestTm','totalTm','bestLap','diff','gap','pitstops','index'}

def query(path, sql, run_id=None):
    meta,fields,rows=read_csv(path)
    if run_id is not None and meta.get('run_id')!=run_id:raise ValueError('CSV不是当前run，拒绝查询')
    meta['query_now']=now()
    if meta.get('collected_at'):
        stamp=dt.datetime.fromisoformat(meta['collected_at'])
        if stamp.tzinfo is None:raise ValueError('采集时间缺少时区')
        age=(dt.datetime.fromisoformat(meta['query_now'])-stamp).total_seconds()
        meta['age_seconds']=round(age,3)
        meta['fresh']=str(-5<=age<=120 and meta.get('status')=='ok').lower()
    else:meta['fresh']='false'
    db=sqlite3.connect(':memory:')
    quote=lambda s:'"'+s.replace('"','""')+'"'
    try:
        db.execute('CREATE TABLE data ('+','.join(quote(f)+(' NUMERIC' if f in NUMERIC else ' TEXT') for f in fields)+')')
        db.executemany('INSERT INTO data VALUES ('+','.join('?' for _ in fields)+')',
                       [[None if r[f]=='' else r[f] for f in fields] for r in rows])
        # Only reading/select/functions; no ATTACH, DDL or writes, even in memory.
        allowed={sqlite3.SQLITE_SELECT,sqlite3.SQLITE_READ,sqlite3.SQLITE_FUNCTION,sqlite3.SQLITE_RECURSIVE}
        db.set_authorizer(lambda action,*args:sqlite3.SQLITE_OK if action in allowed else sqlite3.SQLITE_DENY)
        budget=[0]
        def progress():
            budget[0]+=1
            return budget[0]>10000
        db.set_progress_handler(progress,1000)
        result=db.execute(sql)
        fields=[c[0] for c in result.description]
        rows=result.fetchmany(10001)
        if len(rows)>10000:raise ValueError('查询输出超过10000行，请限制范围')
        text=io.StringIO();writer=csv.writer(text)
        writer.writerow(['# collected_at',meta.get('collected_at','')]+[str(x).replace('\n',' ').replace('\r',' ') for k,v in meta.items() if k!='collected_at' for x in (k,v)])
        writer.writerow(fields);writer.writerows(rows)
        return text.getvalue()
    finally:db.close()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('csv',type=Path);p.add_argument('--sql',default='SELECT * FROM data LIMIT 50')
    p.add_argument('--run-id',help='预期当前运行ID；不匹配则拒绝查询')
    a=p.parse_args();print(query(a.csv,a.sql,a.run_id),end='')
if __name__=='__main__':main()
