import {normalizeAmount} from './extract.mjs';
export const MARKET = {
 id:'istat-enterprises-2024-table-p2',publisher:'ISTAT',title:'Conti economici delle imprese e dei gruppi di impresa — Anno 2024',
 referenceYear:2024,published:'2026-10-15',retrieved:'2026-11-14',page:2,
 url:'https://www.istat.it/wp-content/uploads/2026/10/Conti-economici-imprese-e-gruppi-2024.pdf',localFile:'/sources/istat-2024.pdf',
 population:'Italian enterprises in industry and market services; all included industries and regions, grouped by persons employed.',
 method:'Published aggregate ratios, not the median company or a credit-risk percentile. Turnover per person is calculated from published turnover (EUR millions) and persons employed. Value added/person and labour cost/employee are published, rounded to EUR thousands.',
 limits:'Size-matched only. No sector or regional matching; no national DSCR, debt/EBITDA or LTV benchmark is supplied by this table. Use the same 2024 definitions and period. Persons employed includes working owners; it is not the same denominator as employees.',
 cohorts:[
  {id:'0-9',label:'0–9 persons',min:0,max:9,enterprises:4293094,persons:7377776,employees:3058766,turnoverMillion:893527,valueAddedMillion:296367,valueAddedPerPerson:40200,labourCostPerEmployee:27700},
  {id:'10-19',label:'10–19 persons',min:10,max:19,enterprises:145505,persons:1917116,employees:1742684,turnoverMillion:372407,valueAddedMillion:103025,valueAddedPerPerson:53700,labourCostPerEmployee:34700},
  {id:'20-49',label:'20–49 persons',min:20,max:49,enterprises:62175,persons:1840092,employees:1771794,turnoverMillion:458031,valueAddedMillion:117604,valueAddedPerPerson:63900,labourCostPerEmployee:40100},
  {id:'50-249',label:'50–249 persons',min:50,max:249,enterprises:26527,persons:2587701,employees:2560113,turnoverMillion:854926,valueAddedMillion:199505,valueAddedPerPerson:77100,labourCostPerEmployee:46300},
  {id:'250+',label:'250+ persons',min:250,max:null,enterprises:4752,persons:4585583,employees:4582407,turnoverMillion:1498921,valueAddedMillion:383872,valueAddedPerPerson:83700,labourCostPerEmployee:48900},
  {id:'all',label:'Italy · all sizes',min:0,max:null,enterprises:4532053,persons:18308268,employees:13715764,turnoverMillion:4077812,valueAddedMillion:1100373,valueAddedPerPerson:60100,labourCostPerEmployee:40800}
 ]
};
export const MARKET_FIELDS=[['turnover','Turnover','EUR'],['valueAdded','Value added','EUR'],['labourCost','Labour cost','EUR'],['persons','Persons employed','N'],['employees','Employee count','N']];
export function extractMarket(docs){
 const profile={year:2024,values:{},evidence:{},label:'Extracted historical context; does not affect DMN'};
 for(const [id,label,unit] of MARKET_FIELDS){
  const all=[];
  for(const d of docs)for(const p of d.pages){const re=new RegExp(label+'\\s*\\[2024\\]\\s*:\\s*'+unit+'\\s*([\\d.,]+)','g');for(const m of p.text.matchAll(re)){const v=normalizeAmount(m[1]);if(v!==null)all.push({value:v,documentId:d.id,page:p.number,quote:m[0]});}}
  profile.values[id]=new Set(all.map(x=>x.value)).size===1?all[0].value:null;profile.evidence[id]=all;
 }
 return profile;
}
export function compareMarket(profile,cohortId){
 const n=id=>{const x=profile.values?.[id];return x!==null&&x!==undefined&&x!==''&&Number.isFinite(Number(x))&&Number(x)>=0?Number(x):null;};
 const persons=n('persons'),employees=n('employees');
 const cohort=MARKET.cohorts.find(c=>c.id===cohortId)??MARKET.cohorts.find(c=>c.id!=='all'&&persons!==null&&persons>=c.min&&(c.max===null||persons<c.max+1))??MARKET.cohorts.at(-1);
 const issues=[];
 if(Number(profile.year)!==MARKET.referenceYear)issues.push('The profile year does not match 2024. Direct differences are suppressed.');
 if(persons===null||persons<=0)issues.push('Enter the 2024 average number of persons employed.');
 if(employees!==null&&persons!==null&&employees>persons)issues.push('Employees cannot exceed persons employed under these definitions.');
 if(persons!==null&&cohort.id!=='all'&&(persons<cohort.min||(cohort.max!==null&&persons>=cohort.max+1)))issues.push('The selected size cohort does not match the profile.');
 const ratio=(a,b)=>a!==null&&b!==null&&b>0?a/b:null;
 const specs=[['turnoverPerPerson','Turnover per person',ratio(n('turnover'),persons),cohort.turnoverMillion*1e6/cohort.persons],['valueAddedPerPerson','Value added per person',ratio(n('valueAdded'),persons),cohort.valueAddedPerPerson],['labourCostPerEmployee','Labour cost per employee',ratio(n('labourCost'),employees),cohort.labourCostPerEmployee]];
 const metrics=specs.map(([id,label,actual,reference])=>({id,label,actual,reference,deltaPct:issues.length===0&&actual!==null?(actual/reference-1)*100:null,unit:'EUR',interpretation:id==='labourCostPerEmployee'?'Higher labour cost is not automatically worse; skill mix and sector matter.':'A difference is descriptive economic context, not a credit-risk rating.'}));
 return {datasetId:MARKET.id,cohort,profile,issues,metrics,creditEffect:'NONE — market context never changes the DMN decision.'};
}
