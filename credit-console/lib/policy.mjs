import { createHash } from 'node:crypto';
import { compileModel, loadDmnXml, evaluateModel, toFeelNumber, describeValue } from '@smarthorizon-labs/dmn';

export const ENGINE = '@smarthorizon-labs/dmn@0.1.0';
export const sha = value => createHash('sha256').update(value).digest('hex');
export function canonical(value) {
  if (Array.isArray(value)) return '[' + value.map(canonical).join(',') + ']';
  if (value !== null && typeof value === 'object') return '{' + Object.keys(value).sort().map(k => JSON.stringify(k)+':'+canonical(value[k])).join(',') + '}';
  return JSON.stringify(value);
}
export const SOURCES = [
  {id:'EBA', title:'EBA Guidelines on loan origination and monitoring', version:'EBA/GL/2020/06', sections:'§5.1; §5.2.5 (118–136); §4.3; §5.3; Annex 2.B', file:'/sources/eba.pdf', url:'https://www.eba.europa.eu/sites/default/files/document_library/Publications/Guidelines/2020/Guidelines%20on%20loan%20origination%20and%20monitoring/884283/EBA%20GL%202020%2006%20Final%20Report%20on%20GL%20on%20loan%20origination%20and%20monitoring.pdf'},
  {id:'BDI',title:'Bank of Italy — Supervisory provisions for banks',version:'Circular 285 · update 52 · July 2026',sections:'Part I, Title IV, Chapter 3, Annex A.2 · PDF pp. 412–413',file:'/sources/bdi.pdf',url:'https://www.bancaditalia.it/compiti/vigilanza/normativa/archivio-norme/circolari/c285/index.html'}
];
export const FIELDS = [
 ['cash_available','Cash available for debt service','2027','Cash flow available for debt service'],
 ['existing_principal','Existing principal due','2027','Existing principal due'],
 ['existing_interest','Existing interest due','2027','Existing interest due'],
 ['new_principal','Proposed principal due','2027','Proposed principal due'],
 ['new_interest','Proposed interest due','2027','Proposed interest due'],
 ['debt_after_loan','Post-loan interest-bearing debt','2026-12-31','Post-loan interest-bearing debt'],
 ['ebitda','EBITDA','2026','EBITDA'],
 ['secured_exposure','Secured exposure','2026-12-31','Secured exposure'],
 ['collateral_value','Accepted eligible collateral value','2026-12-31','Accepted eligible collateral value']
].map(([id,label,period,anchor])=>({id,label,period,anchor,currency:'EUR'}));

const common = {
  kind:'DEMO_POLICY',owner:'Demonstration policy — no lender approval',scope:'IT_SMALL_COMPANY_SECURED_TERM_EUR',
  assessmentPeriod:'2027', effectiveFrom:'2026-11-14',effectiveTo:'2027-12-31',
  warning:'Illustrative thresholds selected for this demonstration. They are not EBA or Italian legal cutoffs. Passing these checks is not credit approval.',
  definitions:{dscr:'Cash available / (existing principal + existing interest + proposed principal + proposed interest), all for 2027.',leverage:'Post-loan gross interest-bearing debt / 2026 EBITDA.',ltv:'Secured exposure / bank-accepted eligible collateral value. Ownership, prior claims and valuation treatment require human review.'}
};
export const POLICIES = {
 'demo-v1':{...common,id:'demo-v1',version:'1.0',name:'Demo policy · baseline',thresholds:{minDscr:'1.25',maxLeverage:'3.50',maxLtv:'0.80'}},
 'demo-v2':{...common,id:'demo-v2',version:'2.0',name:'Demo policy · tighter coverage',thresholds:{minDscr:'1.50',maxLeverage:'3.50',maxLtv:'0.80'}},
 'regulatory-only':{...common,id:'regulatory-only',version:'1.0',kind:'UNCONFIGURED',name:'Regulatory framework · no thresholds',thresholds:{minDscr:null,maxLeverage:null,maxLtv:null},warning:'No bank policy supplied. Threshold comparisons must abstain.'}
};
export const RULE_REGISTER = [
 {id:'EVIDENCE_GATE',authority:'Implementation control',basis:'EBA §5.1, paragraphs 84, 86, 89, 94',page:33,source:'EBA',description:'Missing, conflicting, unreviewed or invalid evidence prevents a financial recommendation.'},
 {id:'DSCR_FAIL',authority:'Demo assumption',basis:'EBA §5.2.5, paragraphs 118–120, 128–131 (assessment framework only)',page:38,source:'EBA',description:'Compare defined debt-service coverage with the selected demo minimum.'},
 {id:'LEVERAGE_FAIL',authority:'Demo assumption',basis:'EBA paragraph 128(b), Annex 3 (no universal cutoff)',page:39,source:'EBA',description:'Compare defined leverage with the selected demo maximum.'},
 {id:'LTV_FAIL',authority:'Demo assumption',basis:'EBA paragraph 120, Annex 2.B (no universal cutoff)',page:38,source:'EBA',description:'Compare secured exposure with accepted eligible collateral value. Collateral cannot override a failed cash-flow check.'},
 {id:'PASS_CHECKS',authority:'Implementation control',basis:'EBA §5.3, paragraphs 194–198; Circular 285 Annex A.2',page:50,source:'EBA',description:'All implemented financial checks pass; bank review and approval authority remain required.'}
];
const esc = s=>String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
const literal = (id,name,expr,refs=[],type='number') => `<decision id="${id}" name="${name}"><variable name="${name}" typeRef="${type}"/>${refs.map(([kind,ref])=>`<informationRequirement id="ir_${id}_${ref}"><required${kind} href="#${ref}"/></informationRequirement>`).join('')}<literalExpression id="expr_${id}"><text>${esc(expr)}</text></literalExpression></decision>`;
export function buildDmn(policy) {
 const t=policy.thresholds;
 const val=x=>typeof x==='string'&&/^\d+(\.\d+)?$/.test(x)?x:'null';
 const inputs = [{id:'ready',type:'boolean'},...FIELDS.map(f=>({id:f.id,type:'number'}))];
 const allInputs = inputs.map(i=>`<inputData id="input_${i.id}" name="${i.id}"><variable name="${i.id}" typeRef="${i.type}"/></inputData>`).join('');
 const refs = ids=>[['Input','input_ready'],...ids.map(id=>['Input','input_'+id])];
 const metrics = [
 literal('service','annual_debt_service','if ready then existing_principal + existing_interest + new_principal + new_interest else null',refs(['existing_principal','existing_interest','new_principal','new_interest'])),
 literal('coverage','dscr','if ready then cash_available / annual_debt_service else null',[...refs(['cash_available']),['Decision','service']]),
 literal('leverage_metric','leverage','if ready then debt_after_loan / ebitda else null',refs(['debt_after_loan','ebitda'])),
 literal('ltv_metric','ltv','if ready then secured_exposure / collateral_value else null',refs(['secured_exposure','collateral_value'])),
 literal('dscr_test','dscr_ok',`if ready then dscr >= ${val(t.minDscr)} else false`,[['Input','input_ready'],['Decision','coverage']],'boolean'),
 literal('leverage_test','leverage_ok',`if ready then leverage <= ${val(t.maxLeverage)} else false`,[['Input','input_ready'],['Decision','leverage_metric']],'boolean'),
 literal('ltv_test','ltv_ok',`if ready then ltv <= ${val(t.maxLtv)} else false`,[['Input','input_ready'],['Decision','ltv_metric']],'boolean')
 ].join('');
 const rows=[
  ['EVIDENCE_GATE',['false','-','-','-'],'ABSTAIN'],
  ['DSCR_FAIL',['true','false','-','-'],'FAIL_POLICY_CHECKS'],
  ['LEVERAGE_FAIL',['true','true','false','-'],'FAIL_POLICY_CHECKS'],
  ['LTV_FAIL',['true','true','true','false'],'FAIL_POLICY_CHECKS'],
  ['PASS_CHECKS',['true','true','true','true'],'PASS_POLICY_CHECKS']
 ];
 const decision=`<decision id="final" name="outcome"><variable name="outcome" typeRef="string"/><informationRequirement id="final_ready"><requiredInput href="#input_ready"/></informationRequirement>${['dscr_test','leverage_test','ltv_test'].map(r=>`<informationRequirement id="final_${r}"><requiredDecision href="#${r}"/></informationRequirement>`).join('')}<decisionTable id="credit_decision" hitPolicy="UNIQUE">${['ready','dscr_ok','leverage_ok','ltv_ok'].map((s,i)=>`<input id="col_${i}" label="${s}"><inputExpression typeRef="boolean"><text>${s}</text></inputExpression></input>`).join('')}<output id="outcome_col" typeRef="string"/>${rows.map(([id,tests,out])=>`<rule id="${id}"><description>${esc(RULE_REGISTER.find(r=>r.id===id).description)}</description>${tests.map(x=>`<inputEntry><text>${x}</text></inputEntry>`).join('')}<outputEntry><text>"${out}"</text></outputEntry></rule>`).join('')}</decisionTable></decision>`;
 return `<?xml version="1.0" encoding="UTF-8"?>\n<definitions xmlns="https://www.omg.org/spec/DMN/20230324/MODEL/" id="credit_${policy.id}" name="Credit evidence checks ${policy.version}" namespace="https://credit-console.local/policies/${policy.id}"><description>${esc(policy.warning)}</description>${allInputs}${metrics}${decision}</definitions>`;
}
export function executeDmn(xml, inputs) {
 const compiled=compileModel(loadDmnXml(xml));
 const converted=Object.fromEntries(Object.entries(inputs).map(([k,v])=>[k,typeof v==='string' && /^-?\d+(\.\d+)?$/.test(v)?toFeelNumber(v):v]));
 const result=evaluateModel(compiled,converted,{trace:{level:'RULES'}});
 const decisions={};
 for(const [name,d] of result.decisions) decisions[name]=describeValue(d.value);
 const outcome=decisions.outcome?.replace(/^"|"$/g,'');
 if(!['PASS_POLICY_CHECKS','FAIL_POLICY_CHECKS','ABSTAIN'].includes(outcome)) throw new Error('DMN did not produce a supported outcome: '+JSON.stringify(decisions));
 return {outcome,decisions,matchedRules:(result.trace?.events??[]).filter(e=>e.type==='rule-matched').flatMap(e=>e.ruleIds??[]),trace:result.trace?.events??[]};
}
