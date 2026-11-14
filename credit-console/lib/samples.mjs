export const SAMPLE_VALUES = {cash_available:'140000',existing_principal:'40000',existing_interest:'10000',new_principal:'40000',new_interest:'10000',debt_after_loan:'450000',ebitda:'150000',secured_exposure:'200000',collateral_value:'300000'};
export const SCENARIOS = [
 {id:'complete',name:'Complete packet',description:'Three documents, aligned evidence. Baseline checks pass.',expected:'PASS_POLICY_CHECKS'},
 {id:'missing',name:'Missing repayments',description:'The existing principal schedule is absent. The engine abstains.',expected:'ABSTAIN'},
 {id:'conflict',name:'Conflicting statements',description:'Two sources disagree on the same EBITDA figure.',expected:'ABSTAIN'},
 {id:'weak',name:'Insufficient coverage',description:'Complete evidence, but cash flow falls below the demo threshold.',expected:'FAIL_POLICY_CHECKS'}
];
const header=(title)=>`${title}\nSYNTHETIC DEMONSTRATION — not a real borrower or bank policy.\nApplicant: Officina Aurora S.r.l.\nEntity ID: DEMO-001\nScope: IT_SMALL_COMPANY_SECURED_TERM_EUR\nPrepared: 2026-11-14\nCurrency: EUR; unit: individual euros\n\n`;
export function sampleDocuments(scenario='complete') {
 if(!SCENARIOS.some(s=>s.id===scenario)) throw new Error('Unknown sample scenario');
 const principal=scenario==='missing'?'The existing principal repayment schedule has not been supplied.':'Existing principal due [2027]: EUR 40,000.00';
 const docs=[
  {name:'01-credit-memo.txt',text:header('CREDIT MEMO / CASH-FLOW AND REPAYMENT SCHEDULE')+`The business requests a secured term loan for production equipment. This demonstration uses a 2027 forecast and includes existing and proposed debt service.\n\nCash flow available for debt service [2027]: EUR ${scenario==='weak'?'90,000.00':'140,000.00'}\n${principal}\nExisting interest due [2027]: EUR 10,000.00\nProposed principal due [2027]: EUR 40,000.00\nProposed interest due [2027]: EUR 10,000.00\n\nCash available is the prepared forecast after operating costs, tax, maintenance investment and working-capital changes, before debt service. The assumption has not been independently verified.\n`},
  {name:'02-financial-statements.txt',text:header('FINANCIAL STATEMENTS / MANAGEMENT SUMMARY')+`The following figures describe the specified entity on a standalone basis. The debt balance includes the proposed financing.\n\nEBITDA [2026]: EUR 150,000.00\nPost-loan interest-bearing debt [2026-12-31]: EUR 450,000.00\n\nHistorical context for comparison with ISTAT 2024, separate from the loan assessment:\nTurnover [2024]: EUR 1,800,000.00\nValue added [2024]: EUR 650,000.00\nLabour cost [2024]: EUR 400,000.00\nPersons employed [2024]: N 12\nEmployee count [2024]: N 10\n\nThese are synthetic management figures for demonstrating policy execution.\n`},
  {name:'03-collateral-schedule.txt',text:header('SECURITY / ACCEPTED COLLATERAL SCHEDULE')+`For this fictional case, the assumed eligible collateral value is supplied after the illustrative valuation adjustments and prior claims. The software does not establish legal enforceability.\n\nSecured exposure [2026-12-31]: EUR 200,000.00\nAccepted eligible collateral value [2026-12-31]: EUR 300,000.00\n\nOwnership, valuation, ranking and insurance require a bank reviewer.\n`}
 ];
 if(scenario==='conflict') docs.push({name:'04-revised-financial-memo.txt',text:header('ADDITIONAL FINANCIAL MEMO / UNRESOLVED DIFFERENCE')+'EBITDA [2026]: EUR 120,000.00\nThe relationship between this figure and the earlier statement has not been resolved.\n'});
 return docs;
}
