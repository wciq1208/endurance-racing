ENDPOINTS = {'all_class': 'get-race-result-by-pid', 'control_message': 'get-race-control-by-pid'}

def validate(payload, pid):
    if not isinstance(payload, dict) or str(payload.get('flag')) != '1':
        raise ValueError('接口业务失败：' + str(payload.get('msg', '') if isinstance(payload, dict) else '非对象响应'))
    if not isinstance(payload.get('round'), dict) or str(payload['round'].get('id')) != str(pid):
        raise ValueError('响应场次ID缺失或不匹配，拒绝作为目标比赛数据')
    if not isinstance(payload.get('items'), list):
        raise ValueError('items列表缺失')
    ids = []
    for item in payload['items']:
        if not isinstance(item, dict) or item.get('id') is None:
            raise ValueError('条目缺少id')
        ids.append(str(item['id']))
    if len(set(ids)) != len(ids):
        raise ValueError('条目id重复')
