#!/usr/bin/env python3
"""Archive public radar imagery and render charts; no LLM or precipitation forecast API."""
import argparse
import datetime as dt
import hashlib
import html
import io
import json
import math
from pathlib import Path
import re
import time
import urllib.parse
import urllib.request
import concurrent.futures
import numpy as np
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.ticker import FuncFormatter

CST = dt.timezone(dt.timedelta(hours=8))
ROOT = 'https://img.weather.com.cn/'
PAGE = 'https://www.weather.com.cn/weatherMap/'
BOUNDS = ROOT + 'radarinfo/img_bounds.json'


def jsonp(text, callback):
    match = re.fullmatch(r'\s*' + re.escape(callback) + r'\s*\((.*)\)\s*;?\s*', text, re.S)
    if not match:
        raise ValueError('JSONP结构变化：' + callback)
    return json.loads(match.group(1))


def get(url, direct):
    host = urllib.parse.urlsplit(url).hostname or ''
    if host not in {'img.weather.com.cn', 'i.tq121.com.cn', 'www.nmc.cn', 'image.nmc.cn'}:
        raise ValueError('不支持的数据主机')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({})) if direct else urllib.request.build_opener()
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Referer': PAGE})
    with opener.open(req, timeout=20) as response:
        return response.read(20_000_000)


def cache_image(url, folder, direct):
    key = hashlib.sha256(url.split('?')[0].encode()).hexdigest()[:24]
    suffix = Path(urllib.parse.urlsplit(url).path).suffix.lower()
    path = folder / (key + suffix)
    if not path.exists():
        raw = get(url, direct)
        with Image.open(io.BytesIO(raw)) as im:
            im.verify()
        tmp = path.with_suffix('.tmp')
        tmp.write_bytes(raw)
        tmp.replace(path)
    return path


def frame_time(frame):
    return dt.datetime.strptime(frame['dt'], '%Y%m%d%H%M').replace(tzinfo=CST)


def estimate_shift(a, b, max_shift=30):
    """Global echo-mask translation. This is an experimental image extrapolation."""
    a, b = (a[..., 3] > 127).astype(float), (b[..., 3] > 127).astype(float)
    if min(a.sum(), b.sum()) < 300:
        raise ValueError('有效回波不足，不生成移动预测')
    h, w = a.shape
    shape = (h*2, w*2)
    corr = np.fft.irfft2(np.fft.rfft2(b, s=shape) * np.conj(np.fft.rfft2(a, s=shape)), s=shape)
    shifts = np.arange(-max_shift, max_shift+1)
    window = corr[np.ix_(shifts % shape[0], shifts % shape[1])]
    iy, ix = np.unravel_index(np.argmax(window), window.shape)
    dy, dx = int(shifts[iy]), int(shifts[ix])
    score = float(window[iy, ix]/math.sqrt(a.sum()*b.sum()))
    if score < .55 or max(abs(dy), abs(dx)) == max_shift:
        raise ValueError('回波运动匹配不可靠，不生成预测')
    return np.array([dx, dy], dtype=float), score


def advect(rgba, dx, dy):
    """Translate without wraparound; transparent areas remain unknown/no displayed echo."""
    return np.array(Image.fromarray(rgba).transform((rgba.shape[1], rgba.shape[0]),
        Image.Transform.AFFINE, (1, 0, -dx, 0, 1, -dy), resample=Image.Resampling.NEAREST))


def motion(frames, arrays, clock, max_age=45):
    age = (clock-frame_time(frames[-1])).total_seconds()/60
    if age < -2 or age > max_age:
        raise ValueError(f'最新回波距当前 {age:.1f} 分钟，超过配置的 {max_age} 分钟外推上限')
    if len(frames) < 3:
        raise ValueError('不足三帧回波')
    velocities, scores = [], []
    for i in range(1, len(frames)):
        gap = (frame_time(frames[i])-frame_time(frames[i-1])).total_seconds()/60
        if not 1 <= gap <= 15:
            continue
        try:
            shift, score = estimate_shift(arrays[i-1], arrays[i])
        except ValueError:
            continue
        velocities.append(shift/gap)
        scores.append(score)
    if len(velocities) < 2:
        raise ValueError('连续帧没有至少两段可靠移动估计')
    speed = np.median(velocities, axis=0)
    if max(np.linalg.norm(v-speed) for v in velocities) > 1:
        raise ValueError('连续帧运动不一致，不生成平移预测')
    return speed, min(scores)


def setup_font():
    from radar_fonts import cjk_font
    path = cjk_font()
    if path:
        plt.rcParams['font.family'] = font_manager.FontProperties(fname=path).get_name()
    plt.rcParams['axes.unicode_minus'] = False


def render(frames, arrays, bounds, args, destination, clock):
    setup_font()
    latest = frame_time(frames[-1])
    age = (clock-latest).total_seconds()/60
    forecast, reason = None, ''
    try:
        speed, score = motion(frames, arrays, clock, getattr(args, 'max_source_age', 45))
        forecast = {'velocity_pixels_per_minute': speed.tolist(), 'mask_overlap': score,
                    'kind': 'experimental_global_translation', 'lead_minutes_from_collection': args.leads, 'source_age_minutes': age}
    except ValueError as error:
        reason = str(error)
        # No velocity can be inferred from sparse echoes. Explicit persistence
        # baseline, never a claim that no new rain can appear.
        if -2 <= age <= getattr(args, 'max_source_age', 45) and all(np.count_nonzero(a[...,3]>127)<300 for a in arrays):
            speed = np.zeros(2)
            forecast = {'velocity_pixels_per_minute': [0,0], 'mask_overlap': None,
                        'kind': 'sparse_echo_persistence', 'lead_minutes_from_collection': args.leads,
                        'source_age_minutes': age, 'warning': '仅保持源回波；未测得速度，不代表未来无雨'}
            reason = '稀疏回波：采用保持基线，不声称测得移动速度'
    west, north = bounds[0]
    east, south = bounds[1]
    # Public site gives a bounding box used in a Baidu GroundOverlay. Approximate
    # geographic rendering only; do not claim metre-accurate track positioning.
    merc = lambda lat: math.degrees(math.log(math.tan(math.pi/4+math.radians(lat)/2)))
    extent = (west, east, merc(south), merc(north))
    fig, axes = plt.subplots(2, 2, figsize=(13, 10), facecolor='#f4f7fb')
    age = (clock-latest).total_seconds()/60
    fig.suptitle(f"采集时间 {clock.isoformat(timespec='seconds')}\n{getattr(args, 'case_label', '指定地点附近 · 雷达回波')}\n源帧 {latest:%Y-%m-%d %H:%M} 北京时间 ｜ 数据年龄 {age:.1f} 分钟", fontsize=15)
    for i, ax in enumerate(axes.flat):
        ax.set_facecolor('#e8edf3')
        if i == 0:
            data = arrays[-1]
            title = '最新源帧（不是采集时刻实况）'
        elif forecast:
            lead = args.leads[i-1]
            data = advect(arrays[-1], *(speed*(age+lead)))
            label = '稀疏回波保持' if forecast['kind']=='sparse_echo_persistence' else '回波平移外推'
            title = f'{label} +{lead}分 · {(clock+dt.timedelta(minutes=lead)):%H:%M}\n距源帧累计 {age+lead:.1f} 分钟'
        else:
            ax.axis('off')
            ax.text(.5, .6, f'+{args.leads[i-1]} 分钟外推不可用', ha='center', fontsize=16, transform=ax.transAxes)
            ax.text(.5, .4, reason, ha='center', wrap=True, fontsize=12, transform=ax.transAxes)
            continue
        ax.imshow(data, extent=extent, origin='upper', interpolation='nearest', aspect='auto')
        ax.plot(args.lon, merc(args.lat), marker='+', color='#111827', markersize=13, markeredgewidth=2)
        ax.annotate(getattr(args, 'location_label', '赛车场（近似定位）'), (args.lon, merc(args.lat)), xytext=(8, 8), textcoords='offset points', fontsize=10)
        dx = args.radius_km/(111*math.cos(math.radians(args.lat)))
        dy = args.radius_km/111
        ax.set_xlim(max(west,args.lon-dx), min(east,args.lon+dx))
        ax.set_ylim(merc(max(south,args.lat-dy)), merc(min(north,args.lat+dy)))
        ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f'{math.degrees(2*math.atan(math.exp(math.radians(y)))-math.pi/2):.2f}'))
        ax.set_title(title, fontsize=13)
        ax.set_xlabel('经度（近似）'); ax.set_ylabel('纬度（近似）')
        ax.grid(alpha=.25)
    fig.text(.5, .025, getattr(args, 'source_label', '来源：中国天气网单站雷达')+' ｜ 灰色不保证无雨\n'+(reason or '连续帧速度中位数；外推不预测回波新生/消散。不是官方预报。'), ha='center', fontsize=11)
    legend_path = getattr(args, 'legend_path', None)
    fig.tight_layout(rect=(0,.07,.915 if legend_path else 1,.92))
    if legend_path:
        legend_ax = fig.add_axes([.925,.27,.07,.48])
        legend_ax.imshow(Image.open(legend_path))
        legend_ax.axis('off')
    fig.savefig(destination, dpi=150)
    plt.close(fig)
    return {'available': forecast is not None, 'reason': reason, 'model': forecast,
            'source_time': latest.isoformat(), 'source_age_minutes': age}


def collect(args):
    out = args.output
    raw = out/'raw'; raw.mkdir(parents=True, exist_ok=True)
    clock = dt.datetime.now(CST)
    result = {'collected_at': clock.isoformat(), 'location': {'lat': args.lat, 'lon': args.lon}, 'radar_station': args.station}
    run_id = clock.strftime('%Y%m%d-%H%M%S')
    try:
        bounds = jsonp(get(BOUNDS,args.direct).decode(), 'imgbounds')[args.station]['bound']
        if not bounds[0][0] < args.lon < bounds[1][0] or not bounds[1][1] < args.lat < bounds[0][1]:
            raise ValueError('地点超出雷达图范围')
        entries = jsonp(get(ROOT+'new_radar/json/'+args.station+'.json',args.direct).decode(), 'imgList'+args.station)
        frames = sorted(entries, key=frame_time)[-args.frames:]
        if not frames:
            raise ValueError('没有雷达帧')
        if len({f['dt'] for f in frames}) != len(frames):
            raise ValueError('雷达帧时间重复')
        def download(f):
            name = f['name']
            if Path(name).name != name:
                raise ValueError('无效帧文件名')
            url = ROOT+'new_radar/l/'+name
            path = cache_image(url,raw,args.direct)
            return dict(f, url=url, file='raw/'+path.name), np.array(Image.open(path).convert('RGBA'))
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            downloaded = list(pool.map(download, frames))
        frames, arrays = map(list, zip(*downloaded))
        if len({a.shape for a in arrays}) != 1:
            raise ValueError('雷达帧尺寸不一致')
        legend_for_chart = cache_image('https://i.tq121.com.cn/i/weatherMap/legend_radar.png',raw,args.direct)
        args.legend_path = legend_for_chart
        chart = f'radar-{run_id}.png'
        forecast = render(frames, arrays, bounds, args, out/chart, clock)
        result['radar'] = {'ok': True, 'chart': chart, 'frames': frames, 'bounds': bounds,
                           'nowcast': forecast, 'source': PAGE}
        legend = cache_image('https://i.tq121.com.cn/i/weatherMap/legend_radar.png',raw,args.direct)
        result['radar']['legend'] = 'raw/'+legend.name
    except (OSError, ValueError, KeyError, TypeError) as error:
        result['radar'] = {'ok': False, 'error': str(error)}
    state_tmp = out/'latest.json.tmp'
    state_tmp.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    state_tmp.replace(out/'latest.json')
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--station',required=True)
    p.add_argument('--lat',type=float,required=True)
    p.add_argument('--lon',type=float,required=True)
    p.add_argument('--radius-km',type=float,default=100)
    p.add_argument('--frames',type=int,default=6)
    p.add_argument('--max-source-age',type=float,default=45,help='源帧可外推年龄上限（分钟），默认45')
    p.add_argument('--interval',type=int,default=300,help='轮间休息秒，至少60')
    p.add_argument('--max-polls',type=int,default=0,help='0持续，1仅采一轮')
    p.add_argument('--direct',action='store_true',help='直连国内站点，忽略系统HTTP代理')
    args = p.parse_args(); args.leads = [5,10,20]; args.radar_only = True
    if args.interval<60 or not 3<=args.frames<=24 or args.max_polls<0 or args.radius_km<=0 or not 0<args.max_source_age<=60:
        p.error('interval>=60, frames=3..24, max-polls>=0, radius-km>0')
    count=0
    try:
        while True:
            result=collect(args);count+=1
            print(json.dumps({'time':result['collected_at'],'radar':result['radar']['ok'],'nowcast':result['radar'].get('nowcast'),'waterlogging':result.get('waterlogging',{}).get('status','not_requested')},ensure_ascii=False),flush=True)
            if args.max_polls and count>=args.max_polls:break
            time.sleep(args.interval)
    except KeyboardInterrupt:pass

if __name__=='__main__':main()
