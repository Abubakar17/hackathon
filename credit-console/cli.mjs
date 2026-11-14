import fs from 'node:fs';
import path from 'node:path';
import {runPipeline,replayRecord,getRecord,verifyRecord,listRecords,publicRecord} from './lib/pipeline.mjs';
import {POLICIES,buildDmn} from './lib/policy.mjs';
import {runBenchmark} from './lib/benchmark.mjs';
const [command,arg,...rest]=process.argv.slice(2);
try{
 let output;
 if(command==='demo')output=publicRecord(await runPipeline({scenario:arg||'complete',policyId:rest[0]||'demo-v1'}));
 else if(command==='run'){const names=[arg,...rest].filter(Boolean);output=publicRecord(await runPipeline({files:names.map(n=>({name:path.basename(n),base64:fs.readFileSync(n).toString('base64')}))}));}
 else if(command==='review'){const old=getRecord(arg);if(!Object.values(verifyRecord(old)).every(Boolean))throw new Error('Record integrity failed');output=publicRecord(await runPipeline({frozen:old,parentId:old.id,policyId:old.policy.id,reviewed:true}));}
 else if(command==='replay')output=replayRecord(getRecord(arg));
 else if(command==='verify')output=verifyRecord(getRecord(arg));
 else if(command==='list')output=listRecords();
 else if(command==='benchmark')output=await runBenchmark();
 else if(command==='dmn'){const policy=POLICIES[arg||'demo-v1'];if(!policy)throw new Error('Unknown policy');process.stdout.write(buildDmn(policy));process.exit(0);}
 else {console.log('Credit console commands:\n  node cli.mjs demo complete|missing|conflict|weak [demo-v1|demo-v2]\n  node cli.mjs run document.pdf [more.txt]\n  node cli.mjs review RECORD_ID\n  node cli.mjs replay RECORD_ID\n  node cli.mjs verify RECORD_ID\n  node cli.mjs list\n  node cli.mjs benchmark\n  node cli.mjs dmn demo-v1');process.exit(0);}
 console.log(JSON.stringify(output,null,2));
 if(command==='benchmark'&&output.passed!==output.total)process.exitCode=1;
}catch(e){console.error(e.message);process.exitCode=1;}
