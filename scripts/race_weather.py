#!/usr/bin/env python3
"""Independent radar worker; venue and run identity are supplied by the caller."""
import argparse
import datetime as dt
import portalocker
import io
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
from types import SimpleNamespace


def now():return dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(timespec='milliseconds')

def atomic(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+f'.{os.getpid()}.tmp');tmp.write_bytes(data);tmp.replace(path)

def failure_image(path,meta,label,error):
    path.unlink(missing_ok=True)
    from PIL import Image,ImageDraw,PngImagePlugin
    from radar_fonts import pillow_font
    im=Image.new('RGB',(1500,260),'#f4f7fb');draw=ImageDraw.Draw(im);font=pillow_font(26)
    draw.text((24,18),'采集时间：无成功数据；本轮尝试：'+meta['attempted_at'],font=font,fill='#17243a')
    draw.text((24,80),label+' · 雷达不可用；不代表无雨',font=font,fill='#a62a2a')
    draw.text((24,135),str(error).replace('\n',' ')[:85],font=font,fill='#17243a')
    info=PngImagePlugin.PngInfo()
    for k,v in meta.items():info.add_text(k,str(v))
    buffer=io.BytesIO();im.save(buffer,format='PNG',pnginfo=info);atomic(path,buffer.getvalue())

def meta(args,status,attempted,collected='',**extra):
    return dict(collected_at=collected,attempted_at=attempted,status=status,run_id=args.token,
                run_mode=args.mode,endpoint='weather',lat=args.lat,lon=args.lon,station=args.station,
                location=args.location,**extra)

def once(a):
    from weather_radar_collect import collect
    from PIL import Image,PngImagePlugin
    args=SimpleNamespace(output=a.output/'weather-cache',station=a.station,lat=a.lat,lon=a.lon,
        radius_km=100,frames=6,max_source_age=45,leads=[5,10,20],direct=True,radar_only=True,
        case_label=a.location+'附近 · 雷达回波',location_label=a.location+'（近似定位）',
        source_label='来源：中国天气网单站雷达 '+a.station)
    attempted=now();result=collect(args);radar=result['radar']
    if not radar['ok']:raise RuntimeError(radar['error'])
    info=PngImagePlugin.PngInfo()
    values=meta(a,'ok',attempted,result['collected_at'],source_time=radar['nowcast']['source_time'],
                published_at=now(),nowcast_available=radar['nowcast']['available'])
    for k,v in values.items():info.add_text(k,str(v))
    with Image.open(args.output/radar['chart']) as im:
        buffer=io.BytesIO();im.save(buffer,format='PNG',pnginfo=info)
    atomic(a.output/'radar.png',buffer.getvalue())

def parser():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--lat',type=float,required=True);p.add_argument('--lon',type=float,required=True)
    p.add_argument('--station',required=True);p.add_argument('--location',required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--token',required=True)
    p.add_argument('--mode',choices=['live','test'],default='live')
    p.add_argument('--interval',type=float,default=30);p.add_argument('--once',action='store_true')
    return p

def main():
    p=parser();a=p.parse_args()
    if not math.isfinite(a.lat) or not -90<a.lat<90 or not math.isfinite(a.lon) or not -180<=a.lon<=180:p.error('经纬度无效')
    if not math.isfinite(a.interval) or a.interval<5:p.error('interval must be >=5')
    a.output.mkdir(parents=True,exist_ok=True)
    if a.once:
        with (a.output/'weather.lock').open('a') as lock:
            portalocker.lock(lock,portalocker.LOCK_EX);once(a)
        return
    while True:
        tick=time.monotonic()
        try:
            subprocess.run([sys.executable,str(Path(__file__).resolve()),*sys.argv[1:],'--once'],check=True,timeout=90)
        except Exception as exc:
            traceback.print_exc()
            try:failure_image(a.output/'radar.png',meta(a,'error',now(),error=str(exc)),a.location,exc)
            except Exception:traceback.print_exc()
        time.sleep(max(0,a.interval-(time.monotonic()-tick)))
if __name__=='__main__':main()
