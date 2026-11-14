import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {runBenchmark} from '../lib/benchmark.mjs';
import {runPipeline,replayRecord,verifyRecord} from '../lib/pipeline.mjs';
import {sampleDocuments} from '../lib/samples.mjs';
import {MARKET,compareMarket} from '../lib/market.mjs';
import {normalizeAmount,readDocuments,extractOffline} from '../lib/extract.mjs';

test('20 predefined policy, abstention, integrity and replay cases',async()=>{
 const r=await runBenchmark(); assert.equal(r.passed,r.total,JSON.stringify(r.rows.filter(x=>!x.pass)));assert.equal(r.abstention.unsafePasses,0);
});
test('a real PDF parse abstains until review, then preserves exact source evidence',async()=>{
 const bytes=fs.readFileSync(new URL('../fixtures/complete-packet.pdf',import.meta.url));
 const initial=await runPipeline({files:[{name:'complete-packet.pdf',base64:bytes.toString('base64')}],save:false});
 assert.equal(initial.outcome,'ABSTAIN');assert.equal(initial.review.accepted,false);
 assert.equal(initial.assessment.issues.length,1,JSON.stringify(initial.assessment.issues));
 assert.equal(initial.assessment.issues[0].code,'UNREVIEWED_EVIDENCE');
 const accepted=await runPipeline({frozen:initial,reviewed:true,parentId:initial.id,save:false});
 assert.equal(accepted.outcome,'PASS_POLICY_CHECKS');assert.equal(accepted.evaluation.decisions.dscr,'1.4');
 assert.equal(accepted.evaluation.decisions.annual_debt_service,'100000');
 assert.equal(accepted.assessment.facts.ebitda.observations[0].page,2);
 assert.equal(accepted.marketProfile.values.persons,'12');assert.equal(accepted.parentId,initial.id);
 assert.equal(replayRecord(accepted).same,true);assert.equal(Object.values(verifyRecord(accepted)).every(Boolean),true);
 assert.equal(initial.outcome,'ABSTAIN');
});
for(const scenario of ['missing','conflict','weak'])test(`PDF fixture ${scenario} has its expected result`,async()=>{
 const bytes=fs.readFileSync(new URL(`../fixtures/${scenario}-packet.pdf`,import.meta.url));
 const r=await runPipeline({files:[{name:scenario+'.pdf',base64:bytes.toString('base64')}],reviewed:true,save:false});
 assert.equal(r.outcome,scenario==='weak'?'FAIL_POLICY_CHECKS':'ABSTAIN');
});
test('a second borrower inside the same file cannot bypass the evidence gate',async()=>{
 const docs=sampleDocuments();docs[1].text=docs[1].text.replace('DEMO-001','DEMO-999');
 const r=await runPipeline({files:[{name:'merged.txt',text:docs.map(d=>d.text).join('\n')}],reviewed:true,save:false});
 assert.equal(r.outcome,'ABSTAIN');assert.ok(r.reasons.some(x=>x.code==='OUT_OF_SCOPE'));
});
test('corrupt PDF is a document error and abstains',async()=>{
 const r=await runPipeline({files:[{name:'broken.pdf',base64:Buffer.from('not a pdf').toString('base64')}],reviewed:true,save:false});
 assert.equal(r.outcome,'ABSTAIN');assert.ok(r.reasons.some(x=>x.code==='DOCUMENT_ERROR'));
});
test('Italian and English monetary formats agree; ambiguous punctuation is rejected',()=>{
 assert.equal(normalizeAmount('150.000,00'),'150000');assert.equal(normalizeAmount('150,000.00'),'150000');
 assert.equal(normalizeAmount('150.000'),null);assert.equal(normalizeAmount('1,2,3'),null);
});
test('market ratios use the correct employment denominator and size cohort',()=>{
 const profile={year:2024,values:{persons:12,employees:10,turnover:1800000,valueAdded:650000,labourCost:400000}};
 const result=compareMarket(profile);
 assert.equal(result.cohort.id,'10-19');assert.equal(result.metrics[0].actual,150000);
 assert.equal(result.metrics[0].reference,372407000000/1917116);assert.equal(result.metrics[2].actual,40000);
 assert.equal(result.metrics[1].reference,53700);assert.equal(result.issues.length,0);
 assert.equal(MARKET.cohorts.filter(c=>c.id!=='all').reduce((n,c)=>n+c.enterprises,0),4532053);
});
test('incomparable years, size cohorts and impossible headcounts suppress comparisons',()=>{
 const profile={year:2023,values:{persons:12,employees:10,turnover:1800000}};
 assert.equal(compareMarket(profile).metrics[0].deltaPct,null);
 profile.year=2024;assert.equal(compareMarket(profile,'250+').metrics[0].deltaPct,null);
 profile.values.employees=20;assert.equal(compareMarket(profile).metrics[0].deltaPct,null);
});
test('market scenario edits cannot affect the credit record or its replay',async()=>{
 const r=await runPipeline({scenario:'complete',save:false});const original=JSON.stringify(r);
 compareMarket({year:2024,values:{...r.marketProfile.values,turnover:0}});
 assert.equal(JSON.stringify(r),original);assert.equal(replayRecord(r).same,true);
});
test('AI extraction of a synthetic example still requires review and rejects fabricated quotes',async()=>{
 const candidates=extractOffline(await readDocuments(sampleDocuments())).candidates;
 const originalFetch=globalThis.fetch;
 try {
  globalThis.fetch=async()=>({ok:true,json:async()=>({choices:[{message:{content:JSON.stringify({candidates})}}]})});
  const r=await runPipeline({scenario:'complete',mode:'ai',config:{key:'mock-only',model:'test/model'},save:false});
  assert.equal(r.outcome,'ABSTAIN');assert.equal(r.review.accepted,false);
  candidates[0].quote='Fabricated Cash flow available for debt service [2027]: EUR 140,000.00';
  const fabricated=await runPipeline({scenario:'complete',mode:'ai',config:{key:'mock-only',model:'test/model'},reviewed:true,save:false});
  assert.equal(fabricated.outcome,'ABSTAIN');assert.ok(fabricated.reasons.some(x=>x.code==='INVALID_EVIDENCE'));
 }finally{globalThis.fetch=originalFetch;}
});
