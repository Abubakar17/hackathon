import fs from 'node:fs';
import path from 'node:path';
import {randomUUID} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {FIELDS,POLICIES,ENGINE,SOURCES,buildDmn,executeDmn,sha,canonical} from './policy.mjs';
import {readDocuments,extractOffline,extractAi,normalizeAmount} from './extract.mjs';
import {sampleDocuments} from './samples.mjs';
import {extractMarket,MARKET} from './market.mjs';
export const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
export const DATA=process.env.CREDIT_DATA_DIR || path.join(ROOT,'data');
const REASONS={MISSING_EVIDENCE:'Required evidence is missing.',CONFLICTING_EVIDENCE:'Sources disagree on the same financial fact.',INVALID_EVIDENCE:'Evidence could not be validated.',INVALID_METRIC:'The metric cannot be calculated safely.',POLICY_GAP:'The selected policy has no configured thresholds.',UNREVIEWED_EVIDENCE:'A reviewer must confirm the extracted evidence.',OUT_OF_SCOPE:'The packet is outside the supported scope.',DOCUMENT_ERROR:'A document could not be read.',POLICY_DATE:'The policy is not effective for the assessment date.'};
export function assess(docs,extraction,policy,{reviewed=false,asOf=new Date().toISOString().slice(0,10)}={}) {
 const issues=[],facts={}; const add=(code,field,detail,evidence=[])=>issues.push({code,field,detail,basis:'EBA §5.1 (84, 86, 89); implementation evidence control',evidence});
 if(!Object.values(policy.thresholds).every(v=>typeof v==='string'&&/^\d+(\.\d+)?$/.test(v)&&Number(v)>0))add('POLICY_GAP',null,'Numeric thresholds are not supplied. The two regulatory rulebooks do not supply universal approval cutoffs.');
 if(asOf<policy.effectiveFrom||asOf>policy.effectiveTo)add('POLICY_DATE',null,'Policy is outside its declared demo validity period.');
 const entities=new Set();let applicant='Unnamed applicant';
 for(const doc of docs){
  if(doc.error)add('DOCUMENT_ERROR',null,`${doc.name}: ${doc.error}`);
  const text=doc.pages.map(p=>p.text).join('\n');
  if(!text.trim())add('DOCUMENT_ERROR',null,`${doc.name}: no readable text. OCR is not implemented.`);
  else if(doc.pages.some(p=>!p.text.trim()))add('DOCUMENT_ERROR',null,`${doc.name}: at least one page has no readable text. Check for scanned or blank pages; OCR is not implemented.`);
  const entityMatches=[...text.matchAll(/^Entity ID:[ \t]*(.+)$/gim)].map(m=>m[1].trim());
  const scopeMatches=[...text.matchAll(/^Scope:[ \t]*(.+)$/gim)].map(m=>m[1].trim());
  if(entityMatches.length)entityMatches.forEach(entity=>entities.add(entity));else add('OUT_OF_SCOPE',null,`${doc.name}: add an explicit Entity ID to the packet metadata.`);
  if(!scopeMatches.length||scopeMatches.some(scope=>scope!==policy.scope))add('OUT_OF_SCOPE',null,`${doc.name}: expected Scope: ${policy.scope}.`);
  applicant=text.match(/^Applicant:\s*(.+)$/im)?.[1]?.trim()||applicant;
  if(/(?:unit|amounts?|figures?)\s*[:=]?\s*(?:in\s+)?(?:thousands|millions|EUR\s*000|kEUR)/i.test(text))add('INVALID_EVIDENCE',null,`${doc.name}: scaled amounts are unsupported; provide individual euros.`);
 }
 if(entities.size!==1)add('OUT_OF_SCOPE',null,'The packet must identify exactly one consistent borrower.');
 for(const field of FIELDS){
  const observations=extraction.candidates.filter(c=>c.field===field.id);const valid=[];
  for(const c of observations){
   const doc=docs.find(d=>d.id===c.documentId), page=doc?.pages.find(p=>p.number===c.page);
   let problem=c.invalid;
   if(!page||typeof c.quote!=='string'||c.quote.length<5||!page.text.includes(c.quote))problem='The cited quote is not present on the specified source page.';
   if(!c.value||normalizeAmount(c.rawValue)!==c.value)problem='The numeric value is absent or ambiguous.';
   const tokens=String(c.quote??'').match(/-?\d[\d.,]*/g)??[];
   if(!tokens.some(t=>normalizeAmount(t)===c.value))problem='The numeric value is not present in the cited evidence.';
   if(c.period!==field.period||!String(c.quote).includes(c.period))problem=`Expected period ${field.period}; the evidence period is ${c.period??'missing'}.`;
   if(c.currency!==field.currency||!String(c.quote).includes(c.currency))problem='Evidence must explicitly identify EUR.';
   if(/\b(pending|unverified|provisional|not confirmed|not supplied)\b/i.test(String(c.quote)))problem='Evidence is marked pending or unverified.';
   if(problem)add('INVALID_EVIDENCE',field.id,problem,[c]);else valid.push(c);
  }
  const values=[...new Set(valid.map(c=>c.value))];
  const status=values.length>1?'conflict':values.length===1?'present':'missing';
  facts[field.id]={...field,status,value:values.length===1?values[0]:null,observations};
  if(values.length>1)add('CONFLICTING_EVIDENCE',field.id,`${field.label}: incompatible values ${values.join(' and ')} for ${field.period}.`,valid);
  else if(values.length===0)add('MISSING_EVIDENCE',field.id,`Supply ${field.label.toLowerCase()} for ${field.period}, with EUR units and a source.`,observations);
 }
 if(!reviewed)add('UNREVIEWED_EVIDENCE',null,'Confirm that the values, borrower, periods and evidence match the documents before evaluating the financial policy.');
 const vals=Object.fromEntries(FIELDS.map(f=>[f.id,facts[f.id].value]));
 for(const f of FIELDS){const v=vals[f.id];if(v!==null&&v.startsWith('-')&&f.id!=='cash_available')add('INVALID_METRIC',f.id,`${f.label} cannot be negative in this policy.`);}
 const positive=id=>vals[id]!==null && Number(vals[id])>0;
 for(const id of ['ebitda','collateral_value','secured_exposure'])if(vals[id]!==null&&!positive(id))add('INVALID_METRIC',id,`${facts[id].label} must be positive for this metric definition.`);
 const service=['existing_principal','existing_interest','new_principal','new_interest'];
 if(service.every(id=>vals[id]!==null)&&!service.some(positive))add('INVALID_METRIC','annual_debt_service','Total annual debt service must be positive.');
 return {applicant,entityId:[...entities][0]??null,facts,issues,inputs:{ready:issues.length===0,...vals},asOf};
}
export function evaluateAssessment(assessment,policy) {
 const xml=buildDmn(policy);const evaluation=executeDmn(xml,assessment.inputs);
 const reasons=[...assessment.issues];
 for(const [field,name,rule] of [['dscr','Debt-service coverage','DSCR_FAIL'],['leverage','Leverage','LEVERAGE_FAIL'],['ltv','Collateral LTV','LTV_FAIL']]){
  if(assessment.inputs.ready&&evaluation.decisions[field+'_ok']==='false')reasons.push({code:rule,field,detail:`${name} fails the selected illustrative policy threshold.`,basis:'DEMO_POLICY — not a regulatory cutoff',evidence:[]});
 }
 return {xml,evaluation,reasons};
}
export function semantic(record) {return {inputs:record.assessment.inputs,policyHash:record.policyHash,dmnHash:record.dmnHash,engine:record.engine,outcome:record.outcome,decisions:record.evaluation.decisions,matchedRules:record.evaluation.matchedRules};}
export function seal(record) {record.semanticHash=sha(canonical(semantic(record)));record.integrityHash=sha(canonical(record));return record;}
export function verifyRecord(record) {const {integrityHash,...payload}=record;return {valid:sha(canonical(payload))===integrityHash,modelValid:sha(record.dmn)===record.dmnHash,policyValid:sha(canonical(record.policy))===record.policyHash,semanticValid:sha(canonical(semantic(record)))===record.semanticHash};}
export function storeRecord(record){fs.mkdirSync(path.join(DATA,'records'),{recursive:true});fs.writeFileSync(path.join(DATA,'records',record.id+'.json'),JSON.stringify(record,null,2),{flag:'wx'});fs.appendFileSync(path.join(DATA,'audit.jsonl'),JSON.stringify({id:record.id,hash:record.integrityHash,createdAt:record.createdAt})+'\n');}
export function getRecord(id){if(!/^[a-f0-9-]{36}$/.test(id))throw new Error('Invalid record identifier');return JSON.parse(fs.readFileSync(path.join(DATA,'records',id+'.json'),'utf8'));}
export function listRecords(){const dir=path.join(DATA,'records');if(!fs.existsSync(dir))return [];return fs.readdirSync(dir).filter(n=>n.endsWith('.json')).map(n=>{const r=JSON.parse(fs.readFileSync(path.join(dir,n),'utf8'));return {id:r.id,createdAt:r.createdAt,applicant:r.assessment.applicant,outcome:r.outcome,policy:r.policy.id,parentId:r.parentId,scenario:r.scenario,extractor:r.extraction.engine};}).sort((a,b)=>b.createdAt.localeCompare(a.createdAt));}
export async function runPipeline({files,scenario,policyId='demo-v1',mode='offline',config={},parentId=null,reviewed=false,frozen=null,save=true,asOf}={}) {
 const begin=performance.now(),logs=[];
 const log=(stage,message)=>logs.push({stage,message,elapsedMs:Math.round(performance.now()-begin)});
 const policy=structuredClone(POLICIES[policyId]);if(!policy)throw new Error('Unknown policy');
 let docs,extraction;
 if(frozen){docs=frozen.documents;extraction=frozen.extraction;log('extract','Frozen evidence reused; no language model called.');}
 else {docs=await readDocuments(scenario?sampleDocuments(scenario):files);log('ingest',`${docs.length} documents registered and hashed.`);extraction=mode==='ai'?await extractAi(docs,config):extractOffline(docs);log('extract',`${extraction.candidates.length} candidate observations from ${extraction.engine}.`);}
 const isFixture=Boolean(scenario)&&!frozen;
 const accepted=(isFixture&&mode==='offline')||reviewed;
 const assessment=assess(docs,extraction,policy,{reviewed:accepted,asOf});
 log('validate',`${Object.values(assessment.facts).filter(f=>f.status==='present').length}/${FIELDS.length} fields present; ${assessment.issues.length} blocking issues.`);
 const {xml,evaluation,reasons}=evaluateAssessment(assessment,policy);
 log('decide',`${evaluation.outcome} · DMN rule ${evaluation.matchedRules.join(', ')}.`);
 const explanation=evaluation.outcome==='ABSTAIN'?`No financial recommendation. ${[...new Set(reasons.map(r=>REASONS[r.code]||r.detail))].join(' ')}`:evaluation.outcome==='PASS_POLICY_CHECKS'?'All three implemented financial checks pass the selected demo policy. This is not loan approval; bank underwriting and approval authority remain required.':`The evidence is complete for the implemented checks, but ${reasons.map(r=>r.field).join(', ')} fails the selected demo policy. This is not a formal credit refusal.`;
 const record={schemaVersion:'1.0',id:randomUUID(),createdAt:new Date().toISOString(),parentId,scenario:scenario??null,dataLabel:isFixture?'SYNTHETIC DEMONSTRATION':frozen?.dataLabel??'USER-SUPPLIED — authenticity not verified',review:{accepted,by:isFixture&&mode==='offline'?'Pre-labelled demonstration fixture':reviewed?'Local console reviewer':null},documents:docs,extraction,assessment,policy,policyHash:sha(canonical(policy)),dmn:xml,dmnHash:sha(xml),engine:ENGINE,evaluation,outcome:evaluation.outcome,reasons,explanation,sources:SOURCES,logs};
 record.marketProfile=extractMarket(docs);record.marketDatasetId=MARKET.id;
 log('record','Evidence, policy, model and engine trace captured.');seal(record);if(save)storeRecord(record);return record;
}
export function replayRecord(record){const integrity=verifyRecord(record);if(!Object.values(integrity).every(Boolean))throw new Error('Integrity check failed. Replay stopped.');const run=executeDmn(record.dmn,record.assessment.inputs);const same=canonical({outcome:run.outcome,decisions:run.decisions,matchedRules:run.matchedRules})===canonical({outcome:record.outcome,decisions:record.evaluation.decisions,matchedRules:record.evaluation.matchedRules});return {recordId:record.id,same,integrity,outcome:run.outcome,matchedRules:run.matchedRules,policyId:record.policy.id,message:same?'Exact semantic replay confirmed. No extraction or AI call was performed.':'Replay mismatch: investigate engine or record changes.'};}
export function publicRecord(record){return {...record,documents:record.documents.map(({base64,...d})=>d)};}
