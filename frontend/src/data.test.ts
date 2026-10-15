import contract from './csv-schema.json';
import {readFileSync} from 'node:fs';
import Papa from 'papaparse';
import {describe,it,expect,vi} from 'vitest';
import {parseCSV,statusOf,recentPace,recentLaps,loadData,paceFresh,loadLapBatch} from './data';
const run='0'.repeat(32);
const fixture=(name:string)=>readFileSync(new URL(`../../tests/fixtures/canonical-csv/${name}.csv`,import.meta.url),'utf8');
describe('Python Pydantic CSV -> browser contract',()=>{
 it('uses comma even when many records contain pipe characters',()=>{
  const rows=Papa.parse<string[]>(fixture('results'),{delimiter:',',skipEmptyLines:true}).data;
  const csv=Papa.unparse([rows[0],rows[1],...Array.from({length:30},()=>rows[2].map(cell=>cell.replace('演示,车队','演示 | 车队 | 24H')))]);
  expect(parseCSV(csv,run,'results').rows).toHaveLength(30);
 });
 it('preserves IDs, nulls, escaped sentinel and canonical seconds',()=>{
  const data=parseCSV(fixture('results'),run,'results'),row=data.rows[0];
  expect(row.car_number).toBe('025');expect(row.result_id).toBe('01');
  expect(row.team_name).toBe('演示,车队\\N');expect(row.pit_stops).toBeNull();
  expect(row.best_lap_seconds).toBe(58.69);expect(row.gap_laps).toBe(2);expect(row.gap_seconds).toBeNull();
 });
 it('preserves multiline announcements and distinguishes empty text from null',()=>{
  const row=parseCSV(fixture('control_messages'),run,'control_messages').rows[0];
  expect(row.body).toBe('更正,撤销\n"25号"原处罚\\N');expect(row.published_at_source).toBe('');expect(row.event_time_source).toBeNull();
 });
 it('rejects different run, dataset, schema version and invalid numeric cells',()=>{
  const csv=fixture('results');
  expect(()=>parseCSV(csv,'1'.repeat(32),'results')).toThrow();
  expect(()=>parseCSV(csv,run,'control_messages')).toThrow();
  expect(()=>parseCSV(csv.replace('schema_version"":2','schema_version"":3'),run,'results')).toThrow();
  expect(()=>parseCSV(csv.replace('58.69','NaN'),run,'results')).toThrow();
 });
 it('calculates freshness with the actual clock and rejects future timestamps',()=>{
  vi.useFakeTimers();vi.setSystemTime(new Date('2026-10-15T12:01:00+08:00'));
  const data=parseCSV(fixture('results'),run,'results');expect(statusOf(data.envelope).fresh).toBe(true);
  vi.setSystemTime(new Date('2026-10-15T12:03:00+08:00'));expect(statusOf(data.envelope).fresh).toBe(false);
  vi.setSystemTime(new Date('2026-10-15T11:59:00+08:00'));expect(statusOf(data.envelope).fresh).toBe(false);vi.useRealTimers();
 });
 it('computes pace without including future crossings',()=>{
  const analysis={result_id:'a',status:'ok',analysis_at:'2025-01-01T12:00:00+08:00'} as Parameters<typeof recentPace>[1];
  const laps=[58,59,60,61,62,1].map((s,i)=>({result_id:'a',lap_number:i,crossing_at:`2025-01-01T${i===5?'13':'11'}:00:0${i}+08:00`,lap_seconds:s}));
  expect(recentPace(laps,analysis)).toEqual({samples:5,fastest:58,mean:60,median:60});
 });
 it('uses the last ten completed laps in order, excluding other cars and future data',()=>{
  const analysis={result_id:'a',status:'ok',analysis_at:'2025-01-01T12:00:00+08:00'} as Parameters<typeof recentPace>[1];
  const laps=Array.from({length:12},(_,i)=>({result_id:'a',lap_number:i+1,crossing_at:`2025-01-01T11:${String(i).padStart(2,'0')}:00+08:00`,lap_seconds:50+i}));
  laps.push({result_id:'other',lap_number:20,crossing_at:'2025-01-01T11:59:00+08:00',lap_seconds:1});
  expect(recentLaps(laps,analysis).map(lap=>lap.lap_number)).toEqual([12,11,10,9,8,7,6,5,4,3]);
  expect(recentPace(laps,analysis,10)).toEqual({samples:10,fastest:52,mean:56.5,median:56.5});
  expect(recentLaps(laps,{...analysis,status:'error'})).toEqual([]);
 });
 it('reads previous canonical CSV while emitting the new results lane',()=>{
  const legacy=fixture('results').replace('schema_version"":2','schema_version"":1').replace('lane"":""results','lane"":""all_class');
  const parsed=parseCSV(legacy,run,'results');expect(parsed.envelope.collection.lane).toBe('results');
 });
 it('isolates failed lanes and fails on a switched active run',async()=>{
  const envelope=parseCSV(fixture('results'),run,'results').envelope;
  const manifest=JSON.stringify({run:envelope.run,base:`/race-data/z24-race-manager/${run}/`});
  vi.stubGlobal('fetch',vi.fn(async(url:string)=>new Response(url.endsWith('active.json')?manifest:url.endsWith('results.csv')?fixture('results'):'missing',{status:url.endsWith('active.json')||url.endsWith('results.csv')?200:404})));
  const value=await loadData(new AbortController().signal);expect(value.results).toHaveLength(1);expect(value.collection_status.filter(x=>x.status==='error')).toHaveLength(3);
  let calls=0;vi.stubGlobal('fetch',vi.fn(async(url:string)=>{if(url.endsWith('active.json'))return new Response(++calls===1?manifest:JSON.stringify({run:{run_id:'new'}}));return new Response('missing',{status:404});}));
  await expect(loadData(new AbortController().signal)).rejects.toThrow('运行已切换');vi.unstubAllGlobals();
 });
});

describe('lap observation freshness',()=>{
 it('does not refresh old analysis merely by publishing a slow batch',()=>{
  vi.useFakeTimers();vi.setSystemTime(new Date('2026-10-15T12:01:00+08:00'));
  const envelope=parseCSV(fixture('results'),run,'results').envelope;
  envelope.collection.lane='laps';envelope.collection.collected_at='2026-10-15T12:01:00+08:00';envelope.collection.attempted_at='2026-10-15T11:57:50+08:00';
  expect(statusOf(envelope).fresh).toBe(false);
  envelope.collection.attempted_at='2026-10-15T12:01:00+08:00';envelope.collection.collected_at='2026-10-15T12:02:00+08:00';expect(statusOf(envelope).fresh).toBe(false);
  envelope.collection.collected_at='2026-10-15T12:01:00+08:00';envelope.collection.attempted_at='2026-10-15T12:02:00+08:00';expect(statusOf(envelope).fresh).toBe(false);vi.useRealTimers();
 });
 it('checks per-car timestamps while allowing historical cutoffs in test mode',()=>{
  const now=Date.parse('2026-10-15T12:01:00+08:00');
  const row={status:'ok',analysis_at:'2025-12-21T12:00:00+08:00',received_at:'2026-10-15T12:00:50+08:00'} as Parameters<typeof paceFresh>[0];
  expect(paceFresh(row,'live',now)).toBe(false);expect(paceFresh(row,'test',now)).toBe(true);
  expect(paceFresh({...row,received_at:'2026-10-15T11:57:00+08:00'},'test',now)).toBe(false);
  expect(paceFresh({...row,received_at:'2026-10-15T12:02:00+08:00'},'test',now)).toBe(false);
 });
});

describe('immutable lap batch publication',()=>{
 const snapshot='a'.repeat(32),base=`/race-data/z24-race-manager/${run}/`;
 function csv(dataset:'laps'|'pace',id=snapshot){
  const metadata=Papa.parse<string[]>(fixture('results'),{delimiter:','}).data[0];
  const envelope=JSON.parse(metadata[3]);envelope.dataset=dataset;envelope.snapshot_id=id;envelope.collection.lane='laps';
  return Papa.unparse([[metadata[0],metadata[1],metadata[2],JSON.stringify(envelope)],contract.datasets[dataset].columns]);
 }
 it('reads one pointer and pins both CSV requests to its immutable directory',async()=>{
  const urls:string[]=[];
  vi.stubGlobal('fetch',vi.fn(async(url:string)=>{
   urls.push(url);return new Response(url.endsWith('laps-active.json')?JSON.stringify({snapshot_id:snapshot}):csv(url.endsWith('pace.csv')?'pace':'laps'));
  }));
  try{
   const value=await loadLapBatch(base,run,new AbortController().signal);
   expect(value.envelope.snapshot_id).toBe(snapshot);
   expect(urls).toEqual([base+'laps-active.json',base+`lap-batches/${snapshot}/pace.csv`,base+`lap-batches/${snapshot}/laps.csv`]);
  }finally{vi.unstubAllGlobals();}
 });
 it('rejects unsafe pointers and snapshots inconsistent with the pointer',async()=>{
  for(const pointer of ['../secret',snapshot]){
   vi.stubGlobal('fetch',vi.fn(async(url:string)=>new Response(url.endsWith('laps-active.json')?JSON.stringify({snapshot_id:pointer}):csv(url.endsWith('pace.csv')?'pace':'laps','b'.repeat(32)))));
   try{await expect(loadLapBatch(base,run,new AbortController().signal)).rejects.toThrow();}finally{vi.unstubAllGlobals();}
  }
 });
 it('keeps reading previous canonical runs when no batch pointer exists',async()=>{
  vi.stubGlobal('fetch',vi.fn(async(url:string)=>url.endsWith('laps-active.json')?new Response('missing',{status:404}):new Response(csv(url.endsWith('pace.csv')?'pace':'laps'))));
  try{expect((await loadLapBatch(base,run,new AbortController().signal)).envelope.snapshot_id).toBe(snapshot);}finally{vi.unstubAllGlobals();}
 });
});

describe('independent resource deadlines',()=>{
 const active='/race-data/z24-race-manager/active.json';
 const envelope=parseCSV(fixture('results'),run,'results').envelope;
 const manifest=JSON.stringify({run:envelope.run,base:`/race-data/z24-race-manager/${run}/`});
 function hanging(signal:AbortSignal):Promise<Response>{
  if(signal.aborted)return Promise.reject(signal.reason);
  return new Promise((_,reject)=>signal.addEventListener('abort',()=>reject(signal.reason),{once:true}));
 }
 for(const resource of ['weather.csv','weather-body','laps-active.json','laps.csv','pace.csv']){
  it(`keeps results and announcements when ${resource} hangs`,async()=>{
   vi.useFakeTimers();const controller=new AbortController();let settled=false;
   vi.stubGlobal('fetch',vi.fn(async(url:string,{signal}:{signal:AbortSignal})=>{
    signal.throwIfAborted();
    if(url.endsWith(resource))return hanging(signal);
    if(resource==='weather-body'&&url.endsWith('weather.csv'))return Object.assign(new Response(''),{text:()=>hanging(signal).then(()=> '')});
    if(url===active)return new Response(manifest);
    if(url.endsWith('results.csv'))return new Response(fixture('results'));
    if(url.endsWith('control_messages.csv'))return new Response(fixture('control_messages'));
    if(url.endsWith('pace.csv')||url.endsWith('laps.csv')){
     const dataset=url.endsWith('pace.csv')?'pace':'laps';
     const metadata=Papa.parse<string[]>(fixture('results'),{delimiter:','}).data[0];
     const env=JSON.parse(metadata[3]);env.dataset=dataset;env.collection.lane='laps';
     return new Response(Papa.unparse([[metadata[0],metadata[1],metadata[2],JSON.stringify(env)],contract.datasets[dataset].columns]));
    }
    return new Response('missing',{status:404});
   }));
   const pending=loadData(controller.signal);pending.then(()=>settled=true,()=>settled=true);
   try{
    await vi.advanceTimersByTimeAsync(20000);
    expect(settled).toBe(true);
    const data=await pending;
    expect(data.results).toHaveLength(1);expect(data.control_messages).toHaveLength(1);
    expect(data.collection_status.find(s=>s.lane===(resource.startsWith('weather')?'weather':'laps'))?.status).toBe('error');
    expect(controller.signal.aborted).toBe(false);
    expect(vi.getTimerCount()).toBe(0);
   }finally{controller.abort();await pending.catch(()=>{});vi.useRealTimers();vi.unstubAllGlobals();}
  });
 }
 it('still rejects a switched run after one lane has timed out',async()=>{
  vi.useFakeTimers();let calls=0;
  vi.stubGlobal('fetch',vi.fn(async(url:string,{signal}:{signal:AbortSignal})=>{
   signal.throwIfAborted();
   if(url===active)return new Response(++calls===1?manifest:JSON.stringify({run:{run_id:'changed'}}));
   if(url.endsWith('weather.csv'))return hanging(signal);
   if(url.endsWith('results.csv'))return new Response(fixture('results'));
   return new Response('missing',{status:404});
  }));
  try{
   const assertion=expect(loadData(new AbortController().signal)).rejects.toThrow('运行已切换');
   await vi.advanceTimersByTimeAsync(20000);await assertion;expect(vi.getTimerCount()).toBe(0);
  }finally{vi.useRealTimers();vi.unstubAllGlobals();}
 });
 it('calculates freshness after a slow final identity check',async()=>{
  vi.useFakeTimers();vi.setSystemTime(new Date('2026-10-15T12:01:50+08:00'));let calls=0;
  vi.stubGlobal('fetch',vi.fn(async(url:string)=>{
   if(url===active){if(++calls===2)await new Promise(resolve=>setTimeout(resolve,15000));return new Response(manifest);}
   if(url.endsWith('results.csv'))return new Response(fixture('results'));
   return new Response('missing',{status:404});
  }));
  try{
   const pending=loadData(new AbortController().signal);
   await vi.advanceTimersByTimeAsync(15000);const data=await pending;
   expect(data.collection_status.find(s=>s.lane==='results')?.fresh).toBe(false);
   expect(data.query_now).toBe(new Date('2026-10-15T12:02:05+08:00').toISOString());
   expect(vi.getTimerCount()).toBe(0);
  }finally{vi.useRealTimers();vi.unstubAllGlobals();}
 });
 for(const phase of ['initial','final']){
  it(`bounds a hanging ${phase} run identity check`,async()=>{
   vi.useFakeTimers();let calls=0;
   vi.stubGlobal('fetch',vi.fn(async(url:string,{signal}:{signal:AbortSignal})=>{
    signal.throwIfAborted();
    if(url===active){calls++;return (phase==='initial'||calls===2)?hanging(signal):new Response(manifest);}
    return new Response('missing',{status:404});
   }));
   try{
    const assertion=expect(loadData(new AbortController().signal)).rejects.toMatchObject({name:'TimeoutError'});
    await vi.advanceTimersByTimeAsync(20000);await assertion;
    expect(vi.getTimerCount()).toBe(0);
   }finally{vi.useRealTimers();vi.unstubAllGlobals();}
  });
 }
 it('cancels the whole poll on page disposal and clears deadlines',async()=>{
  vi.useFakeTimers();const controller=new AbortController();const signals:AbortSignal[]=[];
  vi.stubGlobal('fetch',vi.fn(async(url:string,{signal}:{signal:AbortSignal})=>{
   signal.throwIfAborted();if(url===active)return new Response(manifest);
   signals.push(signal);return hanging(signal);
  }));
  try{
   const assertion=expect(loadData(controller.signal)).rejects.toMatchObject({name:'AbortError'});
   await vi.advanceTimersByTimeAsync(0);expect(signals).toHaveLength(4);
   controller.abort();await assertion;
   expect(signals.every(s=>s.aborted)).toBe(true);expect(vi.getTimerCount()).toBe(0);
  }finally{vi.useRealTimers();vi.unstubAllGlobals();}
 });
});
