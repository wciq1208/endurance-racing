"""Read MyRacing public race data using the mini-program's guest request format."""
import hashlib,json,time,urllib.parse,urllib.request
BASE='https://kart.xkarting.com/ajax/wxapi.ashx'
SPECS={
'get-result-realtime':('timeStamp','syskey',['uid']),
'get-race-result-top':('timeStamp','sysKey',['uid']),
'get-race-station-list':('timeStamp','syskey',['uid']),
'get-station-by-id':('timeStamp','syskey',['uid','id']),
'get-race-result-init':('timeStamp','sysKey',['uid','ssid','rid']),
'get-result-realtime-race':('timeStamp','syskey',['uid']),
'get-race-list-group':('timeStamp','syskey',['userId','pid']),
'get-race-result-round-list':('timeStamp','syskey',['userId','pid']),
'get-race-result-ritem-list':('timeStamp','sysKey',['userId']),
'get-race-result-by-pid':('timestamp','syskey',['userId','pid']),
'get-race-result-item':('timestamp','syskey',['userId','pid']),
'get-race-control-by-pid':('timestamp','syskey',['userId','pid']),
'get-race-calendar-init':('timeStamp','syskey',['userId','pid']),
'get-race-round-list':('timeStamp','syskey',['userId','pid']),
'get-race-calendar-list':('timeStamp','syskey',['userId']),
'get-race-docs-init':('timeStamp','syskey',['userId']),
'get-race-docs-list':('timeStamp','syskey',['userId']),
}
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs): return None

def read(flag,**fields):
 tk,sk,keys=SPECS[flag]
 if any(fields.get(k,0)!=0 for k in ['uid','userId','userID']):
  raise ValueError('This helper supports public guest queries only')
 ts=int(time.time()*1000)
 p=dict(fields,flag=flag);p[tk]=ts
 p[sk]=hashlib.md5(('@'+'@'.join(map(str,[flag,ts]+[p[k] for k in keys]))).encode()).hexdigest()
 req=urllib.request.Request(BASE,data=urllib.parse.urlencode(p).encode(),headers={'Content-Type':'application/x-www-form-urlencoded'})
 with urllib.request.build_opener(NoRedirect).open(req,timeout=20) as r: return json.load(r)

if __name__=='__main__':
 import argparse
 a=argparse.ArgumentParser();a.add_argument('flag',choices=SPECS);a.add_argument('params',help='JSON fields; IDs must come from returned lists')
 x=a.parse_args();print(json.dumps(read(x.flag,**json.loads(x.params)),ensure_ascii=False,indent=2))
