import {defineConfig, type Plugin} from 'vite';
import {createReadStream} from 'node:fs';
import {realpath,stat} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import type {IncomingMessage,ServerResponse} from 'node:http';

// Static files only: never expose launcher config, logs or arbitrary workspace paths.
function raceFiles():Plugin{
 const root=fileURLToPath(new URL('../.runtime/public/',import.meta.url));
 const middleware=async(req:IncomingMessage,res:ServerResponse,next:()=>void)=>{
  const url=new URL(req.url||'/','http://localhost');
  if(!url.pathname.startsWith('/race-data/'))return next();
  if(req.method!=='GET'&&req.method!=='HEAD'){res.writeHead(405).end();return;}
  if(!/^\/race-data\/[a-z0-9-]+\/(active\.json|[a-f0-9]{32}\/(results\.csv|control_messages\.csv|laps\.csv|pace\.csv|weather\.csv|radar\.png|laps-active\.json|lap-batches\/[a-f0-9]{32}\/(laps\.csv|pace\.csv)))$/.test(url.pathname)){res.writeHead(404).end();return;}
  try{
   const file=await realpath(path.join(root,url.pathname));
   const realRoot=await realpath(root);
   if(!file.startsWith(realRoot+path.sep)){res.writeHead(404).end();return;}
   if(!(await stat(file)).isFile()){res.writeHead(404).end();return;}
   res.setHeader('Cache-Control','no-store');
   res.setHeader('Content-Type',file.endsWith('.png')?'image/png':file.endsWith('.csv')?'text/csv; charset=utf-8':'application/json');
   if(req.method==='HEAD'){res.end();return;}
   createReadStream(file).on('error',()=>res.destroy()).pipe(res);
  }catch{res.writeHead(404).end();}
 };
 return {name:'race-static-resources',configureServer(server){server.middlewares.use(middleware);},configurePreviewServer(server){server.middlewares.use(middleware);}};
}
export default defineConfig({plugins:[raceFiles()],server:{host:'127.0.0.1'},preview:{host:'127.0.0.1'}});
