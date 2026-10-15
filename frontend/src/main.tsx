import React, {useEffect, useState} from 'react';
import {createRoot} from 'react-dom/client';
import './style.css';
import {loadData,recentPace,recentLaps,paceFresh,type Data} from './data';
const time=(s:string|null)=>s?new Date(s).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false}):'尚无成功数据';
const number=(n:number|null|undefined,digits=3)=>n==null?'—':n.toFixed(digits);
const labels:Record<string,string>={weather:'天气雷达',results:'车队成绩',control_message:'赛会公告',laps:'逐圈与配速'};
export const REFRESH_MS=30000;
function App(){
 const [data,setData]=useState<Data|null>(null),[error,setError]=useState(''),[loading,setLoading]=useState(true),[radarError,setRadarError]=useState(false);
 useEffect(()=>{let disposed=false;let timer:ReturnType<typeof setTimeout>;const controller=new AbortController();
  async function poll(){const started=Date.now();try{const value=await loadData(controller.signal,new URLSearchParams(location.search).get('skill')||'z24-race-manager');if(!disposed){setData(value);setError('');}}
   catch(e){if(!disposed)setError(e instanceof Error?e.message:'读取失败');}
   finally{if(!disposed){setLoading(false);timer=setTimeout(poll,Math.max(0,REFRESH_MS-(Date.now()-started)));}}}
  void poll();return()=>{disposed=true;controller.abort();clearTimeout(timer);};},[]);
 const weather=data?.collection_status.find(s=>s.lane==='weather');
 const lapStatus=data?.collection_status.find(s=>s.lane==='laps');
 const radarUrl=data?`${data.base}radar.png?v=${encodeURIComponent(weather?.attempted_at||data.query_now)}`:'';
 useEffect(()=>setRadarError(false),[radarUrl]);
 return <main><header><div><p className="eyebrow">ENDURANCE RACING / RACE DESK</p><h1>耐力赛车队看板</h1><p>北京时间 · 页面每30秒刷新</p></div><span className="badge">{data?.run.mode==='test'?'历史数据演练':data?'赛事数据':'等待采集'}</span></header>
 {loading&&<p role="status">正在读取赛事数据…</p>}{error&&<div role="alert" className="alert">{error}。{data?'下方保留的是上次读取结果，请勿作为最新赛况。':'请先在 agent 会话中确认赛事与车队并启动采集。'}</div>}
 {data&&<>
 <section className="identity"><div><h2>{data.run.race_name||'赛事'}</h2><p>{data.run.session_name} · 目标车队：{data.run.team}</p><p>场次状态码：{data.run.session_status??'未知'} · 源开赛时间：{data.run.session_start||'未知'}</p></div><div><p>看板读取：{time(data.query_now)}</p><small>Run {data.run.run_id}</small></div></section>
 {data.run.mode==='test'&&<p className="notice">历史成绩及公告不代表当前赛中排名；今天雷达仅验证天气链路。</p>}
 <section className="statuses">{['results','control_message','weather','laps'].map(lane=>{const s=data.collection_status.find(x=>x.lane===lane);return <article key={lane}><h3>{labels[lane]}</h3><strong className={s?.fresh&&!error?'good':'warn'}>{error?'看板读取失败':!s?'尚未补查':s.status==='error'?'采集失败':s.status==='partial'?'部分失败':s.fresh?'数据新鲜':s.status==='waiting'?'等待首轮':'数据陈旧'}</strong><p>成功采集：{time(s?.collected_at||null)}</p>{s?.error&&<small>{s.error}</small>}</article>})}</section>
 <details className="panel collapsible" open><summary>雷达与赛会公告 <span>{data.control_messages.length} 条公告</span></summary>
 <div className="overview-grid">
 <section className="panel radar-panel"><h2>雷达回波</h2><p>成功采集：{time(weather?.collected_at||null)} · 源帧时间见图片。灰色不保证无雨；外推为实验估计。</p>{radarError?<p role="alert">雷达图片不可用，赛事数据仍可查看。</p>:<img key={radarUrl} src={radarUrl} onError={()=>setRadarError(true)} alt="场地附近雷达回波及短时外推，图内标注采集和源帧时间"/>}</section>
 <section className="panel"><h2>赛会公告 <small>{data.control_messages.length} 条</small></h2>
 {!data.control_messages.length&&<p>当前快照无公告；请结合采集状态判断。</p>}
 <div className="scroll announcement-table"><table><thead><tr><th>序号</th><th>发布时间</th><th>事件时间</th><th>公告内容</th></tr></thead><tbody>{data.control_messages.map(m=><tr key={m.message_id}><td>{m.sequence??m.message_id}</td><td>{m.published_at_source||'未知'}</td><td>{m.event_time_source||'未提供'}</td><td className="message-body">{m.body}</td></tr>)}</tbody></table></div></section>
 </div></details>
 <details className="panel collapsible" open><summary>车队成绩与配速 <span>{data.results.length} 支车队</span></summary>
 <p>圈速单位：秒。上一圈及最近10圈来自逐圈补查，按各车分析截止计算；近10圈汇总包含窗口内所有完成圈，最快取其中最短圈速；不足10圈时显示实际样本数。</p>
 <div className="scroll"><table><thead><tr>{['名次','车号','车队','完成圈数','最佳圈','上一圈圈速','近10圈均值 / 中位数 / 最快','前车差距','进站次数','配速截至 / 状态'].map(x=><th key={x}>{x}</th>)}</tr></thead><tbody>{data.results.map(r=>{
  const pace=data.pace.find(p=>p.result_id===r.result_id);
  const recent=pace?recentLaps(data.laps,pace,10):[];
  const stats=pace?recentPace(data.laps,pace,10):null;
  const stale=!!error||!lapStatus?.fresh||!pace||!paceFresh(pace,data.run.mode);
  return <tr key={r.result_id} className={r.team_name===data.run.team?'target':''}>
   <td>{r.position??'—'}</td><td>{r.car_number}</td><td>{r.team_name}</td><td>{r.completed_laps??'—'}</td><td>{number(r.best_lap_seconds)}</td>
   <td>{recent.length?number(recent[0].lap_seconds):'—'}</td>
   <td>{stats?<><div>{number(stats.mean)} / {number(stats.median)} / {number(stats.fastest)}</div><small>{stats.samples}/10圈{stale?' · 数据陈旧或不完整':''}</small></>:'—'}</td>
   <td>{r.gap_laps!==null?`${r.gap_laps} 圈`:r.gap_seconds!==null?`${number(r.gap_seconds)} 秒`:'—'}</td><td>{r.pit_stops??'—'}</td>
   <td>{pace?<><div>{time(pace.analysis_at)}</div><small>{pace.status==='error'?'单车补查失败':pace.status==='no_laps_before_cutoff'?'截止前无逐圈记录':stale?'采集陈旧或部分失败':'本轮补查'} · 收到 {time(pace.received_at)}</small></>:'尚未补查'}</td>
  </tr>;
 })}</tbody></table></div>{!data.results.length&&<p>尚无成功成绩快照。</p>}</details>
 <footer>策略由 agent 读取通用 CSV 与雷达 PNG 后在会话中给出；页面刷新不会触发新的采集或逐圈补查。</footer></>}
 </main>;
}
createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
