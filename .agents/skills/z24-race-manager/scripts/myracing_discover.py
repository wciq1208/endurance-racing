#!/usr/bin/env python3
"""Discover public MyRacing race IDs, without WeChat, an emulator or dependencies."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request

URL = 'https://kart.xkarting.com/ajax/wxapi.ashx'

class DiscoveryError(Exception):
    pass

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

def request(flag, **fields):
    """Normal client guest signature; only three read-only operations allowed."""
    if flag not in {'get-race-list-group', 'get-race-result-round-list',
                    'get-race-result-ritem-list'}:
        raise DiscoveryError('Unsupported operation')
    timestamp = int(time.time() * 1000)
    args = [flag, timestamp, 0]
    if flag != 'get-race-result-ritem-list':
        args.append(fields['pid'])
    signature = hashlib.md5(('@' + '@'.join(map(str, args))).encode()).hexdigest()
    signature_key = 'sysKey' if flag == 'get-race-result-ritem-list' else 'syskey'
    payload = dict(fields, flag=flag, userId=0, timeStamp=timestamp)
    payload[signature_key] = signature
    req = urllib.request.Request(URL, data=urllib.parse.urlencode(payload).encode(),
                                 headers={'Content-Type': 'application/x-www-form-urlencoded'})
    try:
        with urllib.request.build_opener(NoRedirect).open(req, timeout=20) as response:
            data = json.load(response)
    except (OSError, ValueError) as error:
        raise DiscoveryError(f'{flag}: 请求失败 ({error})') from error
    return data

def checked(fetch, flag, **fields):
    data = fetch(flag, **fields)
    if not isinstance(data, dict) or str(data.get('flag')) != '1':
        msg = data.get('msg', '无业务状态') if isinstance(data, dict) else '非对象响应'
        raise DiscoveryError(f'{flag}: 接口未成功：{msg}。不能据此判断赛事未发布。')
    items = data.get('items')
    if not isinstance(items, list):
        raise DiscoveryError(f'{flag}: 响应缺少 items 列表，接口结构可能变化')
    return items

def record(item):
    if not isinstance(item, dict):
        raise DiscoveryError('列表条目不是对象')
    try:
        ident = int(item['id'])
    except (KeyError, ValueError, TypeError) as error:
        raise DiscoveryError('列表条目缺少有效 ID') from error
    if ident <= 0:
        raise DiscoveryError('列表条目 ID 必须为正数')
    return {'id': ident, 'name': str(item.get('name', ''))}

def normalized(value):
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', value)).casefold()

def discover(ssid, year, keyword='24', round_id=None, session_id=None, fetch=request):
    result = {'status': 'not_published', 'queried_at': dt.datetime.now(dt.timezone.utc).isoformat(),
              'ssid': ssid, 'year': year, 'keyword': keyword,
              'available_races': [], 'matched_races': [], 'rounds': [],
              'sessions': [], 'candidates': [], 'selected': None}
    races = checked(fetch, 'get-race-list-group', ssid=ssid, pid=0)
    result['available_races'] = [record(r) for r in races]
    result['matched_races'] = [r for r in result['available_races']
        if re.search(rf'(?<!\d){year}(?!\d)', unicodedata.normalize('NFKC', r['name']))
        and normalized(keyword) in normalized(r['name'])]
    if not result['matched_races']:
        result['message'] = '未找到匹配年度和关键词的公开赛事；请查看 available_races 核对命名。'
        return result
    for race in result['matched_races']:
        rounds = checked(fetch, 'get-race-result-round-list', ssid=ssid, pid=race['id'])
        for raw_round in rounds:
            rnd = record(raw_round)
            result['rounds'].append(dict(rnd, race_id=race['id']))
            if round_id is not None and rnd['id'] != round_id:
                continue
            groups = checked(fetch, 'get-race-result-ritem-list', ssid=ssid, pid=rnd['id'], itemId=0)
            # The client expands one group at a time; fetch omitted groups explicitly.
            expanded_groups = []
            for group in groups:
                grp = record(group)
                if 'ritems' not in group:
                    expanded = checked(fetch, 'get-race-result-ritem-list',
                                       ssid=ssid, pid=rnd['id'], itemId=grp['id'])
                    matching = [g for g in expanded if record(g)['id'] == grp['id']]
                    if not matching:
                        raise DiscoveryError('展开组别后未返回对应组别')
                    group = matching[0]
                sessions = group.get('ritems', [])
                if not isinstance(sessions, list):
                    raise DiscoveryError('ritems 不是列表')
                expanded_groups.append((grp, sessions))
            for grp, sessions in expanded_groups:
                for raw_session in sessions:
                    session = record(raw_session)
                    row = {'ssid': ssid, 'race_id': race['id'], 'race_name': race['name'],
                           'round_id': rnd['id'], 'round_name': rnd['name'],
                           'group_id': grp['id'], 'group_name': grp['name'],
                           'pid': session['id'], 'session_name': session['name'],
                           'type': raw_session.get('type'), 'start_time': raw_session.get('startTime'),
                           'session_status': raw_session.get('status')}
                    result['sessions'].append(row)
                    if str(raw_session.get('type')) == '3' and (session_id is None or session['id'] == session_id):
                        result['candidates'].append(row)
    # Never choose by array order when more than one race session exists.
    unique = {(r['race_id'], r['round_id'], r['pid']): r for r in result['candidates']}
    result['candidates'] = list(unique.values())
    if len(unique) == 1:
        selected = dict(next(iter(unique.values())))
        selected['all_class'] = {'flag': 'get-race-result-by-pid', 'ssid': ssid,
                                'userId': 0, 'pid': selected['pid'], 'isTest': 1, 'group': ''}
        selected['control_message'] = {'flag': 'get-race-control-by-pid', 'ssid': ssid,
                                      'userId': 0, 'pid': selected['pid']}
        result.update(status='ready', selected=selected, message='已找到唯一正赛场次。')
    elif unique:
        result.update(status='ambiguous', message='有多个正赛候选，请根据名称和开赛时间指定 --round-id 或 --session-id。')
    else:
        result.update(status='not_ready', message='已找到年度赛事，但尚无符合筛选条件的正赛；请核对 rounds/sessions 或稍后重试。')
    return result

def positive(value):
    n = int(value)
    if n <= 0:
        raise argparse.ArgumentTypeError('必须为正整数')
    return n

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ssid', type=positive, default=262, help='场地ID，默认262株洲')
    parser.add_argument('--year', type=positive, default=2026, help='赛事年度，默认2026')
    parser.add_argument('--keyword', default='24', help='年度赛事名称包含的文字，默认24')
    parser.add_argument('--round-id', type=positive, help='从候选列表选择届次')
    parser.add_argument('--session-id', type=positive, help='从候选列表选择正赛场次')
    parser.add_argument('--output', type=Path, help='保存JSON；每次覆盖，失败时清除旧 selected，防止误用旧ID')
    args = parser.parse_args()
    try:
        result = discover(args.ssid, args.year, args.keyword, args.round_id, args.session_id)
    except DiscoveryError as error:
        result = {'status': 'error', 'ssid': args.ssid, 'year': args.year,
                  'queried_at': dt.datetime.now(dt.timezone.utc).isoformat(),
                  'selected': None, 'message': str(error)}
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        try:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            tmp = args.output.with_name(args.output.name + f'.{os.getpid()}.tmp')
            tmp.write_text(text + '\n', encoding='utf-8')
            tmp.replace(args.output)
        except OSError as error:
            print(f'无法写入输出文件：{error}', file=sys.stderr)
            return 1
    print(text)
    return {'ready': 0, 'error': 1, 'not_published': 2, 'not_ready': 2, 'ambiguous': 3}[result['status']]

if __name__ == '__main__':
    sys.exit(main())
