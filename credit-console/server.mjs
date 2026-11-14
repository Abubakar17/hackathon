import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import {randomBytes} from 'node:crypto';
import {POLICIES,FIELDS,SOURCES,RULE_REGISTER,ENGINE,buildDmn} from './lib/policy.mjs';
import {ROOT,DATA,runPipeline,getRecord,listRecords,publicRecord,replayRecord,verifyRecord} from './lib/pipeline.mjs';
import {SCENARIOS,sampleDocuments} from './lib/samples.mjs';
import {runBenchmark} from './lib/benchmark.mjs';
import {MARKET,compareMarket} from './lib/market.mjs';

for(const file of [path.join(ROOT,'.env'),path.join(ROOT,'..','.env')])if(fs.existsSync(file)){
 for(const line of fs.readFileSync(file,'utf8').split(/\r?\n/)){const m=line.match(/^([A-Z_]+)\s*=\s*(.*)$/);if(m&&!process.env[m[1]])process.env[m[1]]=m[2].replace(/^['"]|['"]$/g,'');}
}
let gateway={key:process.env.AI_GATEWAY_API_KEY??'',model:process.env.AI_GATEWAY_MODEL??''};
const token=randomBytes(24).toString('hex');
const port=Number(process.env.PORT||8765);
const origin='http://127.0.0.1:'+port;
const reply=(res,status,data)=>{res.writeHead(status,{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'});res.end(JSON.stringify(data));};
const fileReply=(res,file,type,download)=>{if(!fs.existsSync(file)){reply(res,404,{error:'File not found'});return;}res.writeHead(200,{'Content-Type':type,'X-Content-Type-Options':'nosniff',...(download?{'Content-Disposition':`attachment; filename="${path.basename(file)}"`}:{})});fs.createReadStream(file).pipe(res);};
async function body(req){let data='';for await(const chunk of req){data+=chunk;if(data.length>24000000)throw new Error('Packet exceeds the 24 MB request limit');}return JSON.parse(data||'{}');}
const server=http.createServer(async(req,res)=>{
 try{
  if(!['127.0.0.1:'+port,'localhost:'+port].includes(req.headers.host)){reply(res,403,{error:'Localhost access only'});return;}
  const u=new URL(req.url,origin),route=u.pathname;
  if(req.method==='POST'){
   if(req.headers.origin&&!['http://127.0.0.1:'+port,'http://localhost:'+port].includes(req.headers.origin)){reply(res,403,{error:'Cross-origin request rejected'});return;}
   if(req.headers['x-console-token']!==token){reply(res,403,{error:'Reload the console to refresh its session'});return;}
  }
  if(req.method==='GET'&&route==='/api/bootstrap'){reply(res,200,{token,policies:POLICIES,fields:FIELDS,sources:SOURCES,rules:RULE_REGISTER,scenarios:SCENARIOS,engine:ENGINE,gateway:{configured:!!gateway.key,model:gateway.model},market:MARKET,inspiration:'https://github.com/Abubakar17/hackathon/tree/bakar'});return;}
  if(req.method==='GET'&&route==='/api/records'){reply(res,200,listRecords());return;}
  if(req.method==='GET'&&route==='/api/sample'){reply(res,200,{files:sampleDocuments(u.searchParams.get('id')||'complete')});return;}
  if(req.method==='GET'&&route==='/api/market'){reply(res,200,MARKET);return;}
  if(req.method==='GET'&&route==='/api/policy.dmn'){
   const p=POLICIES[u.searchParams.get('id')||'demo-v1'];if(!p)throw new Error('Unknown policy');res.writeHead(200,{'Content-Type':'application/xml','Content-Disposition':`attachment; filename="${p.id}.dmn"`});res.end(buildDmn(p));return;
  }
  const recordMatch=route.match(/^\/api\/records\/([a-f0-9-]{36})(?:\/(export|dmn|document)(?:\/(doc-\d+))?)?$/);
  if(req.method==='GET'&&recordMatch){
   const r=getRecord(recordMatch[1]),action=recordMatch[2];
   if(action==='dmn'){res.writeHead(200,{'Content-Type':'application/xml','Content-Disposition':`attachment; filename="${r.policy.id}.dmn"`});res.end(r.dmn);}
   else if(action==='export'){res.writeHead(200,{'Content-Type':'application/json','Content-Disposition':`attachment; filename="decision-${r.id}.json"`});res.end(JSON.stringify(r,null,2));}
   else if(action==='document'){const d=r.documents.find(d=>d.id===recordMatch[3]);if(!d)throw new Error('Document not found');res.writeHead(200,{'Content-Type':d.name.endsWith('.pdf')?'application/pdf':'text/plain; charset=utf-8','X-Content-Type-Options':'nosniff'});res.end(Buffer.from(d.base64,'base64'));}
   else reply(res,200,publicRecord(r));return;
  }
  if(req.method==='POST'){
   const b=await body(req);
   if(route==='/api/run'){const r=await runPipeline({files:b.files,scenario:b.scenario,policyId:b.policyId,mode:b.mode,config:gateway});reply(res,200,publicRecord(r));return;}
   if(route==='/api/review'){const old=getRecord(b.id);if(!Object.values(verifyRecord(old)).every(Boolean))throw new Error('Record integrity failed');if(!old.review.accepted&&b.acceptEvidence!==true)throw new Error('Review and explicitly accept the extracted evidence before creating a financial assessment.');const r=await runPipeline({frozen:old,parentId:old.id,policyId:b.policyId||old.policy.id,reviewed:true});reply(res,200,publicRecord(r));return;}
   if(route==='/api/replay'){reply(res,200,replayRecord(getRecord(b.id)));return;}
   if(route==='/api/verify'){reply(res,200,verifyRecord(getRecord(b.id)));return;}
   if(route==='/api/benchmark'){const result=await runBenchmark();fs.mkdirSync(DATA,{recursive:true});fs.writeFileSync(path.join(DATA,'benchmark.json'),JSON.stringify(result,null,2));reply(res,200,result);return;}
   if(route==='/api/market/compare'){reply(res,200,compareMarket(b.profile,b.cohortId));return;}
   if(route==='/api/config'){if(typeof b.key!=='string'||b.key.length>500||typeof b.model!=='string'||!b.model.includes('/'))throw new Error('Enter a gateway key and a provider/model identifier');gateway={key:b.key,model:b.model.trim()};reply(res,200,{configured:!!gateway.key,model:gateway.model,message:'Saved in this server process only. Key is never returned to the browser.'});return;}
  }
  if(req.method==='GET'&&route.startsWith('/sources/')){const name=route.slice(9);if(!['eba.pdf','bdi.pdf','istat-2024.pdf'].includes(name))throw new Error('Unknown source');fileReply(res,path.join(ROOT,'sources',name),'application/pdf');return;}
  if(req.method==='GET'&&route.startsWith('/fixtures/')){const name=path.basename(route);if(!/^[a-z0-9_-]+\.pdf$/.test(name))throw new Error('Invalid fixture');fileReply(res,path.join(ROOT,'fixtures',name),'application/pdf',true);return;}
  const staticFiles={'/':'index.html','/app.js':'app.js','/style.css':'style.css'};
  if(req.method==='GET'&&staticFiles[route]){fileReply(res,path.join(ROOT,'public',staticFiles[route]),route.endsWith('.js')?'text/javascript; charset=utf-8':route.endsWith('.css')?'text/css; charset=utf-8':'text/html; charset=utf-8');return;}
  reply(res,404,{error:'Not found'});
 }catch(e){reply(res,400,{error:e.message||'Request failed'});}
});
server.listen(port,'127.0.0.1',()=>console.log(`Credit Decision Console running at ${origin}`));
server.on('error',e=>{console.error(e.code==='EADDRINUSE'?'Port already in use. Set PORT to another local port.':e.message);process.exitCode=1;});
