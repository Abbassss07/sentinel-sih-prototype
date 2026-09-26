import { useEffect, useState } from 'react'
import { ArrowLeft, ArrowRight, Blocks, Check, ChevronDown, Download, FileCheck2, ScanFace, ShieldAlert, ShieldCheck, Upload, UserRoundCheck } from 'lucide-react'

const API = '/api'
const steps = [
  ['Document', 'Review synthetic test document'],
  ['MRZ checks', 'Validate extracted document fields'],
  ['Liveness', 'Confirm live presence'],
  ['Face check', 'Compare reference and live capture'],
  ['Ledger', 'Verify credential record'],
  ['Decision', 'Record officer decision'],
]

function App() {
  const [scenarios, setScenarios] = useState([])
  const [scenarioKey, setScenarioKey] = useState('genuine')
  const [caseId, setCaseId] = useState(null)
  const [step, setStep] = useState(0)
  const [ledger, setLedger] = useState(null)
  const [action, setAction] = useState('')
  const [note, setNote] = useState('')
  const [actionSaved, setActionSaved] = useState(false)
  const [report, setReport] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => { fetch(`${API}/scenarios`).then(r => r.json()).then(setScenarios).catch(() => setError('The local API is unavailable. Start the FastAPI server and refresh.')) }, [])
  const scenario = scenarios.find(item => item.key === scenarioKey)

  async function openCase() {
    setError('')
    const response = await fetch(`${API}/cases`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ scenario_key: scenarioKey }) })
    if (!response.ok) return setError('Unable to open the seeded test case.')
    const data = await response.json()
    setCaseId(data.case_id); setStep(0); setLedger(null); setAction(''); setNote(''); setActionSaved(false); setReport(null)
  }

  async function loadLedger() {
    const response = await fetch(`${API}/cases/${caseId}/ledger-proof`)
    if (response.ok) setLedger(await response.json())
  }

  async function saveAction() {
    setError('')
    const response = await fetch(`${API}/cases/${caseId}/action`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action, note }) })
    if (response.ok) setActionSaved(true)
    else setError((await response.json()).detail || 'Unable to record the officer decision.')
  }

  async function generateReport() {
    setError('')
    const response = await fetch(`${API}/cases/${caseId}/report`, { method: 'POST' })
    if (response.ok) setReport(await response.json())
    else setError((await response.json()).detail || 'Unable to generate the report.')
  }

  if (!caseId) return <CaseStart scenarios={scenarios} scenarioKey={scenarioKey} setScenarioKey={setScenarioKey} openCase={openCase} error={error} />
  if (!scenario) return null
  return <main className="app-shell">
    <Header caseId={caseId} />
    <div className="prototype-banner"><ShieldAlert size={16}/><span><strong>Prototype mode.</strong> This case contains only seeded synthetic/test data. SENTINEL does not make automated decisions.</span></div>
    <CaseBar scenario={scenario} step={step} />
    <section className="workspace">
      <Stepper current={step} />
      <StepContent scenario={scenario} step={step} ledger={ledger} loadLedger={loadLedger} action={action} setAction={setAction} note={note} setNote={setNote} actionSaved={actionSaved} saveAction={saveAction} report={report} generateReport={generateReport} error={error} />
      <div className="flow-nav">
        <button className="secondary" onClick={() => setStep(Math.max(0, step - 1))} disabled={step === 0}><ArrowLeft size={16}/>Back</button>
        {step < steps.length - 1 ? <button className="primary" disabled={step === 4 && !ledger} onClick={() => setStep(step + 1)}>Continue<ArrowRight size={16}/></button> : null}
      </div>
    </section>
  </main>
}

function Header({ caseId }) { return <header className="topbar"><div className="brand"><ShieldCheck size={20}/><span>SENTINEL</span><small>IDENTITY ASSURANCE</small></div><div className="top-status"><span><Blocks size={15}/> Permissioned ledger: test adapter</span><span>{caseId}</span></div></header> }

function CaseStart({ scenarios, scenarioKey, setScenarioKey, openCase, error }) {
  return <main className="start-shell"><div className="start-header"><div className="brand"><ShieldCheck size={20}/><span>SENTINEL</span><small>IDENTITY ASSURANCE</small></div></div><section className="case-launcher"><p className="eyebrow">SYNTHETIC / TEST ENVIRONMENT</p><h1>Start a screening case</h1><p className="lede">Choose one of the three seeded demonstrations. Each case makes a specific verification outcome visible without using real identity records.</p><label htmlFor="scenario">Test scenario</label><div className="select-wrap"><select id="scenario" value={scenarioKey} onChange={e => setScenarioKey(e.target.value)}>{scenarios.map(item => <option value={item.key} key={item.key}>{item.title}</option>)}</select><ChevronDown size={16}/></div>{error && <p className="error">{error}</p>}<button className="primary start-button" onClick={openCase} disabled={!scenarios.length}>Open test case <ArrowRight size={16}/></button><p className="microcopy">No raw passport image, face image, or biometric template is stored on the simulated ledger.</p></section></main>
}

function CaseBar({ scenario, step }) { return <div className="case-bar"><div><p className="eyebrow">CASE IN PROGRESS</p><h1>{scenario.title}</h1><p>{scenario.credential_id} · North Terminal · Gate 3</p></div><div className={`level ${scenario.risk_level.toLowerCase()}`}>{step === 5 ? `Suggested: ${scenario.risk_level}` : 'In review'}</div></div> }

function Stepper({ current }) { return <ol className="stepper">{steps.map(([label], index) => <li key={label} className={index < current ? 'complete' : index === current ? 'active' : ''}><span>{index < current ? <Check size={13}/> : index + 1}</span><b>{label}</b></li>)}</ol> }

function StepContent(props) {
  const { scenario, step } = props
  if (step === 0) return <section className="step-panel"><StepHeading icon={<Upload/>} title="Document intake" copy="Upload or capture a passport-like synthetic test document. In this prototype, the selected scenario supplies a non-sensitive test record."/><div className="document-placeholder"><FileCheck2 size={38}/><strong>Synthetic test passport record</strong><span>Credential {scenario.credential_id}</span></div><Evidence title="Document fields read" items={[`Holder: ${scenario.holder_name}`, `Date of birth: ${scenario.date_of_birth}`, 'Issuer: Republic of Testland (synthetic)']} /></section>
  if (step === 1) return <section className="step-panel"><StepHeading icon={<FileCheck2/>} title="OCR and MRZ-like checks" copy="The production pipeline will extract fields with EasyOCR and validate MRZ structure and cross-field consistency. This seeded case models the resulting evidence."/><Evidence title="Check results" items={scenario.document_checks}/><Limitations/></section>
  if (step === 2) return <section className="step-panel"><StepHeading icon={<ScanFace/>} title="Live presence challenge" copy="Ask the traveller to turn their head left, then return to centre. MediaPipe will be used to detect the challenge completion locally during capture."/><div className="camera-box"><ScanFace size={48}/><span>Camera preview is connected in the next integration milestone</span></div><Evidence title="Challenge evidence" items={scenario.liveness_checks}/></section>
  if (step === 3) return <section className="step-panel"><StepHeading icon={<UserRoundCheck/>} title="Face verification" copy="A lightweight ONNX-compatible model will compare the credential reference and the live capture. This prototype reports a decision outcome, not a confidence metric."/><Evidence title="Result" items={[scenario.face_check]}/><Limitations/></section>
  if (step === 4) return <LedgerStep {...props}/>
  return <DecisionStep {...props}/>
}

function StepHeading({ icon, title, copy }) { return <><div className="step-heading"><span className="step-icon">{icon}</span><div><h2>{title}</h2><p>{copy}</p></div></div></> }
function Evidence({ title, items }) { return <div className="evidence"><h3>{title}</h3>{items.map(item => <div className="evidence-row" key={item}><Check size={16}/><span>{item}</span></div>)}</div> }
function Limitations() { return <aside className="limitation"><ShieldAlert size={16}/><span><strong>Prototype limitation:</strong> this result is based on a seeded test scenario. It is not a production assessment.</span></aside> }

function LedgerStep({ scenario, ledger, loadLedger }) { return <section className="step-panel"><StepHeading icon={<Blocks/>} title="Permissioned-ledger verification" copy="Only a credential hash, status, issuer trace, and audit transaction are represented here—never passport images or biometric data."/>{!ledger ? <button className="primary ledger-button" onClick={loadLedger}>Verify credential against ledger</button> : <div className="ledger-proof"><div><p className="eyebrow">VERIFICATION PROOF</p><h2>{ledger.status}</h2><p>Credential {ledger.credential_id}</p></div><dl><div><dt>Document hash</dt><dd>{ledger.document_hash_match ? 'MATCHED' : 'MISMATCH'}</dd></div><div><dt>Transaction ID</dt><dd className="mono">{ledger.transaction_id}</dd></div><div><dt>Recorded</dt><dd>{new Date(ledger.recorded_at).toLocaleString()}</dd></div><div><dt>Adapter</dt><dd>{ledger.adapter}</dd></div></dl></div>}<Limitations/></section> }

function DecisionStep({ scenario, action, setAction, note, setNote, actionSaved, saveAction, report, generateReport, error }) { return <section className="step-panel"><StepHeading icon={<ShieldCheck/>} title="Officer decision" copy="Review the evidence and record your decision. The system provides reasons, but the officer retains authority."/><div className="risk-summary"><p className="eyebrow">EXPLAINABLE RISK FINDINGS</p><h2 className={scenario.risk_level.toLowerCase()}>{scenario.risk_level}</h2>{scenario.risk_reasons.map(reason => <div className="reason" key={reason}>{reason}</div>)}</div><div className="actions"><h3>Final action</h3><div className="action-options">{['CLEAR', 'ESCALATE', 'HOLD'].map(value => <button key={value} className={action === value ? 'selected' : ''} disabled={actionSaved} onClick={() => setAction(value)}>{value}</button>)}</div><label htmlFor="note">Officer note <span>(optional)</span></label><textarea id="note" value={note} disabled={actionSaved} onChange={e => setNote(e.target.value)} placeholder="Record a concise reason or handoff note." rows="3"/><button className="primary" disabled={!action || actionSaved} onClick={saveAction}>{actionSaved ? 'Decision recorded' : 'Record officer decision'}</button>{error && <p className="error" role="alert">{error}</p>}{actionSaved && <div className="report-next"><p>Decision saved to the audit trail. Generate the detailed case report when ready.</p><button className="primary" disabled={!!report} onClick={generateReport}>{report ? 'Report generated' : 'Generate final report'}</button>{report && <div className="report-result"><span>Report {report.id} is stored with this case.</span><a className="report-download" href={report.download_url}><Download size={16}/> Download PDF</a><small>SHA-256: {report.sha256}</small></div>}</div>}</div></section> }

export default App
