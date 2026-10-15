"""MyRacing-specific conversion into the shared canonical schema."""
import json
from race_live_common import ROOT
from race_data.models import Result, ControlMessage, Collection


def optional(value, cast=str):
    return None if value is None or value=='' else cast(value)


def gap(value):
    value=optional(value,float)
    if value is None:return None,None
    if value<0:
        if not value.is_integer():raise ValueError('Lap deficit must be an integer')
        return None,int(-value)
    return value/1000,None


def result(row):
    seconds,laps=gap(row.get('gap'));leader_seconds,leader_laps=gap(row.get('diff'))
    known={'id','carNo','carTeam','nicname','carClass','pos','pic','laps','bestTm','totalTm','bestLap','gap','diff','pitstops','st'}
    private={'name','photo','userid','userId','openid','unionid','phone','mobile'}
    return Result(result_id=str(row['id']),car_number=str(row['carNo']),
        team_name=str(row.get('carTeam') or row.get('nicname') or ''),driver_name=optional(row.get('nicname')),
        class_name=optional(row.get('carClass')),position=optional(row.get('pos'),int),
        class_position=optional(row.get('pic'),int),completed_laps=optional(row.get('laps'),int),
        best_lap_seconds=optional(row.get('bestTm'),lambda v:float(v)/1000),
        total_seconds=optional(row.get('totalTm'),lambda v:float(v)/1000),best_lap_number=optional(row.get('bestLap'),int),
        gap_seconds=seconds,gap_laps=laps,leader_gap_seconds=leader_seconds,leader_gap_laps=leader_laps,
        pit_stops=optional(row.get('pitstops'),int),source_status=optional(row.get('st')),
        extra_json=json.dumps({k:v for k,v in row.items() if k not in known|private and not isinstance(v,(dict,list))},ensure_ascii=False))


def message(row):
    return ControlMessage(message_id=str(row['id']),sequence=optional(row.get('index'),int),
        published_at_source=optional(row.get('c_time')),event_time_source=optional(row.get('time')),body=str(row.get('cont','')))


def collection(meta):
    return Collection(run_id=meta['run_id'],lane='results' if meta['endpoint']=='all_class' else meta['endpoint'],status=meta['status'],
        attempted_at=meta['attempted_at'],collected_at=meta.get('collected_at') or None,
        error=meta.get('error',''),metadata_json=json.dumps(meta,ensure_ascii=False))
