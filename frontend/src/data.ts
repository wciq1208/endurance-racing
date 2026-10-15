import Papa from 'papaparse';
import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import contract from './csv-schema.json';

const ajv=new Ajv2020({strict:false});addFormats(ajv);
const validateEnvelope=ajv.compile(contract.envelope),validateRun=ajv.compile(contract.run);
type Schema={type?:string;anyOf?:Schema[]};
type Dataset=keyof typeof contract.datasets;
const validators=Object.fromEntries(Object.entries(contract.datasets).map(([k,v])=>[k,ajv.compile(v.schema)]));
export type Run={run_id:string;team:string;race_name:string;session_name:string;mode:string;session_status:string|null;session_start:string|null};
export type Status={lane:string;status:string;fresh:boolean;collected_at:string|null;attempted_at:string;age_seconds:number|null;error:string};
export type Result={result_id:string;car_number:string;team_name:string;position:number|null;completed_laps:number|null;best_lap_seconds:number|null;gap_seconds:number|null;gap_laps:number|null;pit_stops:number|null};
export type Message={message_id:string;sequence:number|null;published_at_source:string|null;event_time_source:string|null;body:string};
export type Pace={result_id:string;car_number:string;team_name:string;status:string;analysis_at:string;received_at:string;pace_median_seconds:number|null;crossing_age_seconds:number|null};
type Envelope={schema_version:2;dataset:Dataset;snapshot_id:string;run:Run;collection:{run_id:string;lane:string;status:string;attempted_at:string;collected_at:string|null;error:string}};
export type Lap={result_id:string;lap_number:number;crossing_at:string;lap_seconds:number};
export type Parsed={envelope:Envelope;rows:Record<string,unknown>[]};

function cell(value:string,schema:Schema):unknown{
 if(value==='\\N')return null;
 const text=value.replaceAll('\\\\','\\');
 const type=schema.type||schema.anyOf?.find(s=>s.type!=='null')?.type;
 if(type==='number'||type==='integer'){
  if(!/^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?$/.test(text))throw new Error('无效CSV数值');
  const number=Number(text);if(!Number.isFinite(number)||(type==='integer'&&!Number.isSafeInteger(number)))throw new Error('无效CSV数值');return number;
 }
 if(type==='boolean'){if(!['true','false'].includes(text))throw new Error('无效CSV布尔值');return text==='true';}
 return text;
}

export function parseCSV(text:string,runId:string,dataset:Dataset):Parsed{
 const parsed=Papa.parse<string[]>(text,{skipEmptyLines:true,delimiter:','});
 if(parsed.errors.length)throw new Error('CSV解析失败');
 const [meta,header,...lines]=parsed.data;
 if(meta?.length!==4||meta[0]!=='# collected_at'||meta[2]!=='envelope')throw new Error('CSV元数据错误');
 const raw=JSON.parse(meta[3]);
 // Read the previous canonical contract during rolling collector updates.
 if(raw.schema_version===1){raw.schema_version=2;if(raw.collection?.lane==='all_class')raw.collection.lane='results';}
 const envelope=raw as Envelope;
 if(!validateEnvelope(envelope)||envelope.dataset!==dataset||envelope.run.run_id!==runId||envelope.collection.run_id!==runId)throw new Error('CSV版本、类型或run不匹配');
 if(envelope.collection.collected_at?Date.parse(meta[1])!==Date.parse(envelope.collection.collected_at):meta[1]!=='')throw new Error('CSV采集时间不匹配');
 const lane={results:'results',control_messages:'control_message',laps:'laps',pace:'laps',weather:'weather'}[dataset];
 if(envelope.collection.lane!==lane)throw new Error('CSV采集路不匹配');
 const spec=contract.datasets[dataset];
 if(JSON.stringify(header)!==JSON.stringify(spec.columns))throw new Error('CSV列不符合Pydantic模型');
 const properties=spec.schema.properties as Record<string,Schema>;
 const rows=lines.map(line=>{
  if(line.length!==header.length)throw new Error('CSV行宽错误');
  const row=Object.fromEntries(header.map((name,i)=>[name,cell(line[i],properties[name])]));
  if(!validators[dataset](row))throw new Error('CSV记录未通过通用模型校验');
  return row;
 });
 return {envelope,rows};
}

export function statusOf(envelope:Envelope):Status{
 const c=envelope.collection;let age=c.collected_at?(Date.now()-Date.parse(c.collected_at))/1000:null;
 let clockValid=age!==null&&age>=-5;
 if(age!==null&&c.lane==='laps'){const attemptAge=(Date.now()-Date.parse(c.attempted_at))/1000;clockValid=clockValid&&attemptAge>=-5;age=Math.max(age,attemptAge);}
 return {...c,age_seconds:age,fresh:c.status==='ok'&&clockValid&&age!==null&&age<=(c.lane==='weather'?240:120)};
}
async function read(url:string,signal:AbortSignal){const response=await fetch(url,{cache:'no-store',signal});if(!response.ok)throw new Error(`资源不可用 HTTP ${response.status}`);return response.text();}
// Scope each deadline to one lane or one identity check. The caller signal is
// reserved for page disposal, so one slow resource cannot cancel its peers.
async function withDeadline<T>(parent:AbortSignal,work:(signal:AbortSignal)=>Promise<T>):Promise<T>{
 parent.throwIfAborted();
 const deadline=new AbortController();
 const timer=setTimeout(()=>deadline.abort(new DOMException('资源读取超时','TimeoutError')),20000);
 const signal=AbortSignal.any([parent,deadline.signal]);
 try{return await work(signal);}
 finally{clearTimeout(timer);deadline.abort();}
}
export type Data={query_now:string;run:Run;collection_status:Status[];results:Result[];control_messages:Message[];pace:Pace[];laps:Lap[];base:string};
export async function loadData(signal:AbortSignal,skill='z24-race-manager'):Promise<Data>{
 if(!/^[a-z0-9][a-z0-9-]{0,63}$/.test(skill))throw new Error('赛事skill格式错误');
 const activeUrl=`/race-data/${skill}/active.json`;
 const manifest=JSON.parse(await withDeadline(signal,s=>read(activeUrl,s)));
 if(!validateRun(manifest.run)||manifest.base!==`/race-data/${skill}/${manifest.run.run_id}/`||!/^[a-f0-9]{32}$/.test(manifest.run.run_id))throw new Error('运行指针格式错误');
 const names:Dataset[]=['results','control_messages','weather','pace'];
 const loaded=await Promise.allSettled(names.map(name=>withDeadline(signal,async laneSignal=>{
  if(name==='pace')return loadLapBatch(manifest.base,manifest.run.run_id,laneSignal);
  const data=parseCSV(await read(manifest.base+name+'.csv',laneSignal),manifest.run.run_id,name);
  return {...data,lapRows:[] as Record<string,unknown>[]};
 })));
 const end=JSON.parse(await withDeadline(signal,s=>read(activeUrl,s)));if(end.run?.run_id!==manifest.run.run_id)throw new Error('运行已切换，下轮重试');
 const result:Data={query_now:new Date().toISOString(),run:manifest.run,collection_status:[],results:[],control_messages:[],pace:[],laps:[],base:manifest.base};
 loaded.forEach((item,index)=>{
  const name=names[index];
  if(item.status==='rejected'){
   result.collection_status.push({lane:{results:'results',control_messages:'control_message',weather:'weather',pace:'laps',laps:'laps'}[name],status:'error',fresh:false,collected_at:null,attempted_at:result.query_now,age_seconds:null,error:String(item.reason)});return;
  }
  result.collection_status.push(statusOf(item.value.envelope));
  if(name==='results')result.results=item.value.rows as unknown as Result[];
  if(name==='control_messages')result.control_messages=item.value.rows as unknown as Message[];
  if(name==='pace'){result.pace=item.value.rows as unknown as Pace[];result.laps=item.value.lapRows as unknown as Lap[];}
 });
 result.results.sort((a,b)=>(a.position??Infinity)-(b.position??Infinity));
 result.control_messages.sort((a,b)=>(b.sequence??0)-(a.sequence??0));
 return result;
}

export function recentLaps(laps:Lap[],analysis:Pace,count=10){
 if(analysis.status!=='ok')return [];
 return laps.filter(r=>r.result_id===analysis.result_id&&Date.parse(r.crossing_at)<=Date.parse(analysis.analysis_at))
  .sort((a,b)=>Date.parse(b.crossing_at)-Date.parse(a.crossing_at)).slice(0,count);
}

export function recentPace(laps:Lap[],analysis:Pace,count=5){
 const recent=recentLaps(laps,analysis,count).map(r=>r.lap_seconds);
 if(!recent.length)return null;
 const sorted=[...recent].sort((a,b)=>a-b),n=sorted.length;
 return {samples:n,fastest:sorted[0],mean:recent.reduce((a,b)=>a+b,0)/n,median:n%2?sorted[(n-1)/2]:(sorted[n/2-1]+sorted[n/2])/2};
}

export function paceFresh(analysis:Pace,mode:string,now=Date.now()){
 const recent=(stamp:string)=>{const age=(now-Date.parse(stamp))/1000;return Number.isFinite(age)&&age>=-5&&age<=120;};
 return analysis.status==='ok'&&recent(analysis.received_at)&&(mode==='test'||recent(analysis.analysis_at));
}

export async function loadLapBatch(base:string,runId:string,signal:AbortSignal){
 const response=await fetch(base+'laps-active.json',{cache:'no-store',signal});
 let snapshot:string|null=null;
 if(response.status!==404){
  if(!response.ok)throw new Error(`逐圈指针不可用 HTTP ${response.status}`);
  const state=JSON.parse(await response.text());
  if(typeof state.snapshot_id!=='string'||!/^[a-f0-9]{32}$/.test(state.snapshot_id))throw new Error('逐圈指针格式错误');
  snapshot=state.snapshot_id;
 }
 const pinned=snapshot?`${base}lap-batches/${snapshot}/`:base;
 const [pace,laps]=await Promise.all(['pace','laps'].map(async name=>parseCSV(await read(pinned+name+'.csv',signal),runId,name as Dataset)));
 if(pace.envelope.snapshot_id!==laps.envelope.snapshot_id||(snapshot&&pace.envelope.snapshot_id!==snapshot))throw new Error('逐圈批次不匹配');
 return {...pace,lapRows:laps.rows};
}
