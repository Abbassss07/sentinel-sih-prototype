import { useCallback, useEffect, useState } from 'react'
import { Activity, ArrowLeft, ArrowRight, Blocks, Check, ChevronRight, ClipboardList, Download, Fingerprint, Plus, ScanFace, ShieldAlert, ShieldCheck, X } from 'lucide-react'

const API = '/api'
const STEPS = ['Document', 'Liveness', 'Face', 'Ledger', 'Decision']
const LABELS = { genuine: 'Genuine credential', edited_document: 'Edited document', wrong_person: 'Wrong person' }
const time = value => value ? new Date(value).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' }) : '—'
const short = value => value ? `${value.slice(0, 12)}…${value.slice(-8)}` : '—'

async function api(path, options) {
  const response = await fetch(`${API}${path}`, options)
  const result = await response.json()
  if (!response.ok) throw new Error(result.detail || 'Request failed')
  return result
}
const post = (path, body = {}) => api(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })

export default function SentinelApp() {
  const [view, setView] = useState('overview')
  const [period, setPeriod] = useState('today')
  const [overview, setOverview] = useState(null)
  const [registry, setRegistry] = useState(null)
  const [scenarios, setScenarios] = useState([])
  const [caseData, setCaseData] = useState(null)
  const [step, setStep] = useState(0)
  const [error, setError] = useState('')
  const reloadOverview = useCallback(async value => setOverview(await api(`/overview?period=${value}`)), [])
  const reloadRegistry = useCallback(async () => setRegistry(await api('/registry')), [])
  const reloadCase = useCallback(async id => setCaseData(await api(`/cases/${id}`)), [])

  useEffect(() => {
    Promise.all([api('/scenarios'), reloadOverview('today'), reloadRegistry()])
      .then(([items]) => setScenarios(items))
      .catch(err => setError(err.message))
  }, [reloadOverview, reloadRegistry])

  async function navigate(next) {
    setView(next); setError('')
    try { if (next === 'overview') await reloadOverview(period); if (next === 'registry' || next === 'audit') await reloadRegistry() }
    catch (err) { setError(err.message) }
  }
  async function choosePeriod(value) {
    setPeriod(value)
    try { await reloadOverview(value) } catch (err) { setError(err.message) }
  }
  async function startCase(key) {
    try {
      setError('')
      const created = await post('/cases', { scenario_key: key })
      await reloadCase(created.case_id)
      await reloadOverview(period)
      setStep(0); setView('case')
    } catch (err) { setError(err.message) }
  }

  const titles = { overview: 'Screening overview', new: 'Start a screening', case: 'Screening case', registry: 'Credential registry', audit: 'Ledger audit trail' }
  return <div className="app-layout">
    <aside className="sidebar">
      <div className="brand"><div className="brand-icon"><ShieldCheck size={20}/></div><div><strong>SENTINEL</strong><span>IDENTITY ASSURANCE</span></div></div>
      <div className="nav-label">OPERATIONS</div>
      <nav aria-label="Primary navigation">
        <button className={`nav-item ${view === 'overview' ? 'active' : ''}`} onClick={() => navigate('overview')}><Activity size={17}/> Overview</button>
        <button className={`nav-item ${view === 'new' || view === 'case' ? 'active' : ''}`} onClick={() => navigate('new')}><ScanFace size={17}/> Screenings</button>
        <button className={`nav-item ${view === 'registry' ? 'active' : ''}`} onClick={() => navigate('registry')}><Blocks size={17}/> Credential registry</button>
        <button className={`nav-item ${view === 'audit' ? 'active' : ''}`} onClick={() => navigate('audit')}><ClipboardList size={17}/> Audit trail</button>
      </nav>
      <div className="side-footer"><strong>SIH26188 · FIRST-ROUND DEMO</strong><span>All identities and credentials are fictional.</span><span>Local simulator · no Fabric network</span></div>
    </aside>
    <main className="main-area"><header className="topbar"><div><div className="breadcrumb">Operations / {view === 'case' ? caseData?.case.id : titles[view]}</div><h1>{titles[view]}</h1></div><div className="header-meta"><span className="connection"><span className="connection-dot"/> Local ledger simulator</span><span>North Terminal · Gate 3</span></div></header>
      <div className="main-content"><div className="prototype-banner"><ShieldAlert size={17}/><span><b>Prototype demonstration.</b> Synthetic identities only. OCR, camera liveness, and face outcomes are seeded; MRZ checks, rule points, audit records, and registry hash checks run in code.</span></div>
        {error && <div className="error-banner" role="alert"><span>{error}</span><button aria-label="Dismiss error" onClick={() => setError('')}><X size={16}/></button></div>}
        {view === 'overview' && <Overview data={overview} period={period} onPeriod={choosePeriod} onNew={() => navigate('new')} onRegistry={() => navigate('registry')}/>}
        {view === 'new' && <CasePicker scenarios={scenarios} onStart={startCase}/>}
        {view === 'case' && caseData && <Screening key={caseData.case.id} data={caseData} step={step} setStep={setStep} refresh={() => reloadCase(caseData.case.id)} onNew={() => navigate('new')} setError={setError}/>}
        {view === 'registry' && <Registry data={registry} refresh={reloadRegistry} setError={setError}/>}
        {view === 'audit' && <Audit data={registry}/>}
      </div>
    </main>
  </div>
}

function Status({ value }) { return <span className={`status ${String(value || '').toLowerCase().replaceAll(' ', '-')}`}><span/>{value || 'PENDING'}</span> }
function Metric({ label, value, note, tone }) { return <div className="metric"><span>{label}</span><strong className={tone || ''}>{value}</strong><small>{note}</small></div> }
function Field({ label, value, mono }) { return <div className="field"><span>{label}</span><b className={mono ? 'mono' : ''}>{value ?? '—'}</b></div> }

function Overview({ data, period, onPeriod, onNew, onRegistry }) {
  if (!data) return <div className="loading">Loading shift activity…</div>
  return <><div className="section-head"><div><h2>Shift activity</h2><p>Screenings and ledger events from the selected period</p></div><div className="segmented" aria-label="Activity period">{[['today','Today'],['week','This week'],['month','This month']].map(([key,label]) => <button key={key} className={period === key ? 'selected' : ''} onClick={() => onPeriod(key)}>{label}</button>)}</div></div>
    <div className="metric-row"><Metric label="Screenings opened" value={data.screenings} note="Synthetic test environment"/><Metric label="Ledger checks" value={data.ledger_checks} note="Recorded verification events"/><Metric label="Requires review" value={data.attention} note="Cases for officer attention" tone="risk"/></div>
    <div className="overview-grid"><section className="surface"><div className="surface-head"><div><h3>Recent screenings</h3><span>Current synthetic case activity</span></div><button className="text-button" onClick={onNew}>New screening <ArrowRight size={15}/></button></div><div className="table-wrap"><table><thead><tr><th>Case</th><th>Scenario</th><th>Finding</th><th>Opened</th></tr></thead><tbody>{data.recent_cases.length ? data.recent_cases.map(item => <tr key={item.id}><td className="mono">{item.id}</td><td>{LABELS[item.scenario_key]}</td><td><Status value={item.suggested_level}/></td><td>{time(item.created_at)}</td></tr>) : <tr><td colSpan="4" className="empty-cell">No screenings in this period.</td></tr>}</tbody></table></div></section>
      <section className="surface trust-surface"><div className="surface-head"><div><h3>Shared credential trust</h3><span>Latest test registry activity</span></div><Blocks size={18}/></div><div className="trust-inner"><div className="chain-state"><span className={`state-dot ${data.chain.intact ? 'ok' : 'bad'}`}/><div><b>{data.chain.intact ? 'Hash chain intact' : 'Hash chain issue'}</b><small>{data.chain.event_count} linked test events</small></div></div><div className="trust-flow"><span>Issuer</span><ChevronRight size={15}/><span>Checkpoint</span><ChevronRight size={15}/><span>Review authority</span></div><div className="mini-proof"><small>LATEST EVENT</small>{data.recent_events[0] ? <><b>{data.recent_events[0].event_type} · {data.recent_events[0].credential_id}</b><span>{data.recent_events[0].transaction_id}</span></> : <span>No events yet.</span>}</div><button className="text-button" onClick={onRegistry}>View registry <ArrowRight size={15}/></button></div></section></div>
    <div className="callout"><div><strong>Three-case demonstration</strong><span>Run one genuine screening, then compare the edited document and wrong person findings. Finish with the registry transaction and PDF report.</span></div><button className="primary" onClick={onNew}>Start guided screening <ArrowRight size={16}/></button></div>
  </>
}

function CasePicker({ scenarios, onStart }) { return <><div className="section-head"><div><h2>Choose a synthetic case</h2><p>Three controlled scenarios make the evidence and officer decision easy to compare.</p></div></div><div className="scenario-grid">{scenarios.map((item,index) => <article className="scenario-card" key={item.key}><div className="scenario-number">0{index + 1} / TEST CASE</div><h3>{item.title}</h3><p>{item.description}</p><div className="scenario-facts"><span>Document</span><b>{item.key === 'edited_document' ? 'Visible field edited' : 'Issuer record intact'}</b><span>Person</span><b>{item.key === 'wrong_person' ? 'Reference mismatch' : 'Reference consistent'}</b></div><button className="primary" onClick={() => onStart(item.key)}>Open case <ArrowRight size={16}/></button></article>)}</div><p className="subtle-note">All records and people in these cases are fictional.</p></> }

function StepHeading({ number, title, text }) { return <div className="step-heading"><span>{number} / SCREENING</span><h3>{title}</h3><p>{text}</p></div> }
function Passport({ document }) { return <div className="passport"><div className="passport-top"><span>REPUBLIC OF TESTLAND</span><span>FICTIONAL TEST DOCUMENT</span></div><div className="passport-watermark">SPECIMEN</div><div className="passport-body"><div className="portrait"><Fingerprint size={44}/><span>TEST PORTRAIT</span></div><div className="passport-fields"><small>TYPE / ISSUING STATE</small><strong>P · TST</strong><small>SURNAME / GIVEN NAMES</small><strong>{document.holder_name.toUpperCase()}</strong><div><span><small>DOCUMENT NO.</small><strong>{document.passport_number}</strong></span><span><small>DATE OF BIRTH</small><strong>{document.date_of_birth}</strong></span></div><div><span><small>EXPIRY</small><strong>{document.expiry_date}</strong></span><span><small>NATIONALITY</small><strong>TESTLAND</strong></span></div></div></div><div className="mrz-lines"><div>{document.mrz_line_1}</div><div>{document.mrz_line_2}</div></div></div> }

function Screening({ data, step, setStep, refresh, onNew, setError }) {
  const { case: record, scenario, checks, ledger, risk, report } = data
  const [left, setLeft] = useState(false)
  const [centre, setCentre] = useState(false)
  const [action, setAction] = useState(record.officer_action || '')
  const [note, setNote] = useState(record.officer_note || '')
  const [busy, setBusy] = useState(false)
  async function run(path, body) { setBusy(true); setError(''); try { await post(`/cases/${record.id}/${path}`, body); await refresh() } catch (err) { setError(err.message) } finally { setBusy(false) } }
  const done = [!!checks.document_check, !!checks.liveness, !!checks.face_check, !!ledger, !!record.officer_action]
  return <><div className="case-heading"><div><button className="back-link" onClick={onNew}><ArrowLeft size={15}/> All test cases</button><div className="case-kicker">{record.id} · NORTH TERMINAL / GATE 3</div><h2>{scenario.title}</h2><p>{scenario.description}</p></div><Status value={record.officer_action || risk?.level || 'IN PROGRESS'}/></div><div className="case-shell"><ol className="stepper">{STEPS.map((name,index) => <li key={name} className={index === step ? 'active' : done[index] ? 'complete' : ''}><span>{done[index] ? <Check size={12}/> : index + 1}</span><b>{name}</b></li>)}</ol><div className="step-body">
    {step === 0 && <><StepHeading number="01" title="Document and MRZ examination" text="Read the synthetic document fields and validate its machine readable zone."/><div className="document-grid"><Passport document={scenario.document}/><div className="check-panel"><h3>Field extraction</h3><p className="source-label">SEEDED SYNTHETIC DATA · NO OCR MODEL RUN</p><Field label="Holder" value={scenario.document.holder_name}/><Field label="Document ID" value={scenario.document.passport_number}/><Field label="Visible birth date" value={scenario.document.date_of_birth}/><Field label="MRZ birth date" value={scenario.document.mrz.fields.birth_date}/>{checks.document_check ? <div className="result-box"><div><Check size={16}/> TD3 check digits {checks.document_check.mrz.checksums_valid ? 'valid' : 'invalid'}</div><div className={checks.document_check.mrz.cross_field_match ? '' : 'warn'}>{checks.document_check.mrz.cross_field_match ? <Check size={16}/> : <ShieldAlert size={16}/>} Visible fields {checks.document_check.mrz.cross_field_match ? 'match' : 'differ from'} MRZ</div></div> : <button className="primary" disabled={busy} onClick={() => run('document-check')}>Run MRZ checks <ArrowRight size={16}/></button>}</div></div></>}
    {step === 1 && <><StepHeading number="02" title="Live presence challenge" text="Walk through the two actions an officer would request at the camera."/><div className="challenge-grid"><div className="camera-demo"><ScanFace size={54}/><strong>Demo capture station</strong><span>Camera analysis is not active in this build</span></div><div className="check-panel"><h3>Challenge sequence</h3><p className="source-label">GUIDED SIMULATION · NO MEDIAPIPE INFERENCE</p><button className={`challenge-action ${left ? 'done' : ''}`} onClick={() => setLeft(true)} disabled={!!checks.liveness}>1. Traveller turns left {left && <Check size={16}/>}</button><button className={`challenge-action ${centre ? 'done' : ''}`} onClick={() => setCentre(true)} disabled={!left || !!checks.liveness}>2. Traveller returns to centre {centre && <Check size={16}/>}</button>{checks.liveness ? <div className="result-box"><Check size={16}/> Demo challenge completed and recorded</div> : <button className="primary" disabled={!left || !centre || busy} onClick={() => run('liveness', { turned_left:left, returned_center:centre })}>Record challenge</button>}</div></div></>}
    {step === 2 && <><StepHeading number="03" title="Reference person comparison" text="A valid document can still be presented by the wrong person."/><div className="face-grid"><div className="person-tile"><Fingerprint size={40}/><span>Issuer reference</span><b>{scenario.holder_name}</b></div><div className="compare-divider">VS</div><div className="person-tile"><ScanFace size={40}/><span>Checkpoint capture</span><b>{scenario.key === 'wrong_person' ? 'Different test person' : 'Matching test person'}</b></div></div><div className="comparison-footer"><p className="source-label">SEEDED OUTCOME · ONNX FACE MODEL NOT RUN</p>{checks.face_check ? <Status value={checks.face_check.reference_match ? 'MATCH' : 'MISMATCH'}/> : <button className="primary" disabled={busy} onClick={() => run('face-check')}>Run demo comparison <ArrowRight size={16}/></button>}</div></>}
    {step === 3 && <><StepHeading number="04" title="Credential registry verification" text="The checkpoint hashes the presented fields and compares the result with the issuer's record."/><div className="ledger-explainer"><span>Presented fields</span><ArrowRight size={17}/><span>SHA-256 digest</span><ArrowRight size={17}/><span>Issuer record + status</span></div>{ledger ? <div className="proof-card"><div className="proof-lead"><div><p className="source-label">RECORDED EVENT · LOCAL SIMULATOR</p><h3>{ledger.status}</h3><span>{ledger.issuer || 'No issuing record'}</span></div><Status value={ledger.document_hash_match === true ? 'HASH MATCH' : ledger.document_hash_match === false ? 'HASH MISMATCH' : 'NOT FOUND'}/></div><Field label="Credential ID" value={ledger.credential_id}/><Field label="Transaction" value={ledger.transaction_id} mono/><Field label="Issued hash" value={short(ledger.credential_hash)} mono/><Field label="Presented hash" value={short(ledger.presented_hash)} mono/><Field label="Event hash" value={short(ledger.event_hash)} mono/><Field label="Recorded" value={time(ledger.recorded_at)}/></div> : <div className="ledger-prompt"><Blocks size={38}/><p>Run the check to write a verification event and view its transaction proof.</p><button className="primary" disabled={busy} onClick={() => run('ledger-proof')}>Verify credential <ArrowRight size={16}/></button></div>}<p className="subtle-note">This is a local hash-linked simulator. Hyperledger Fabric is the intended multi-organization deployment layer.</p></>}
    {step === 4 && <><StepHeading number="05" title="Officer decision and report" text="Rule points explain the findings. The officer records the final action."/>{risk && <div className="decision-grid"><div className="risk-card"><p className="source-label">DETERMINISTIC RULES · NOT MODEL CONFIDENCE</p><div className="risk-main"><Status value={risk.level}/><strong>{risk.points}<small> / 100 points</small></strong></div>{risk.reasons.map(reason => <div className="risk-reason" key={reason}>{reason}</div>)}</div><div className="decision-card"><h3>Officer action</h3><div className="action-options">{['CLEAR','ESCALATE','HOLD'].map(value => <button className={action === value ? 'selected' : ''} key={value} disabled={!!record.officer_action} onClick={() => setAction(value)}>{value}</button>)}</div><label htmlFor="officer-note">Officer note <span>(optional)</span></label><textarea id="officer-note" rows="3" value={note} disabled={!!record.officer_action} onChange={e => setNote(e.target.value)} placeholder="Add a concise decision or handoff note."/>{!record.officer_action ? <button className="primary" disabled={!action || busy} onClick={() => run('action', {action,note})}>Record officer decision</button> : <div className="saved-decision"><Check size={17}/> {record.officer_action} recorded in audit trail</div>}{record.officer_action && <div className="report-area">{report ? <><strong>Final report stored in case database</strong><small>{report.id} · SHA-256 {short(report.sha256)}</small><a href={report.download_url} className="primary link-button"><Download size={16}/> Download PDF report</a></> : <><p>The report includes every check, transaction proof, reasons, and decision.</p><button className="primary" disabled={busy} onClick={() => run('report')}>Generate final report <ArrowRight size={16}/></button></>}</div>}</div></div>}</>}
    </div><div className="step-nav"><button className="secondary" disabled={step === 0} onClick={() => setStep(step - 1)}><ArrowLeft size={16}/> Back</button><span>{step + 1} of {STEPS.length}</span>{step < STEPS.length - 1 ? <button className="primary" disabled={!done[step]} onClick={() => setStep(step + 1)}>Continue <ArrowRight size={16}/></button> : <button className="secondary" onClick={onNew}>Another case <ArrowRight size={16}/></button>}</div></div></>
}

function Registry({ data, refresh, setError }) {
  const [id,setId] = useState('TST-DEMO-001')
  const [holder,setHolder] = useState('Mira Das')
  const [birth,setBirth] = useState('1991-11-06')
  const [lookup,setLookup] = useState('TST-0200')
  const [proof,setProof] = useState(null)
  const [busy,setBusy] = useState(false)
  async function act(path,body) { setBusy(true);setError('');try {const result=await post(path,body);await refresh();return result}catch(err){setError(err.message);return null}finally{setBusy(false)} }
  if (!data) return <div className="loading">Loading registry…</div>
  return <><div className="section-head"><div><h2>Shared test credential state</h2><p>Issue, verify, and revoke a synthetic credential with traceable authority events.</p></div><span className="source-label">LOCAL HASH-LINKED SIMULATOR · NOT FABRIC</span></div><div className="registry-grid"><section className="surface"><div className="surface-head"><div><h3>Registered credentials</h3><span>Hashes, status, issuer, and event metadata</span></div></div><div className="table-wrap"><table><thead><tr><th>Credential</th><th>Issuer</th><th>Status</th><th>Action</th></tr></thead><tbody>{data.credentials.map(item => <tr key={item.credential_id}><td className="mono">{item.credential_id}</td><td>{item.issuer}</td><td><Status value={item.status}/></td><td>{item.status === 'VALID' && !['TST-0042','TST-0097'].includes(item.credential_id) ? <button className="text-button danger" disabled={busy} onClick={() => act(`/registry/${item.credential_id}/revoke`)}>Revoke</button> : '—'}</td></tr>)}</tbody></table></div></section><section className="surface registry-form"><div className="surface-head"><div><h3>Register test credential</h3><span>Issuer: Test Passport Authority</span></div><Plus size={18}/></div><div className="form-inner"><label>Test credential ID<input value={id} onChange={e => setId(e.target.value.toUpperCase())}/></label><label>Fictional holder<input value={holder} onChange={e => setHolder(e.target.value)}/></label><label>Date of birth<input type="date" value={birth} onChange={e => setBirth(e.target.value)}/></label><button className="primary" disabled={busy} onClick={() => act('/registry',{credential_id:id,holder_name:holder,date_of_birth:birth})}>Register hash and status <ArrowRight size={16}/></button><small>Raw document images and biometrics are never submitted here.</small></div></section></div><section className="surface lookup-surface"><div className="surface-head"><div><h3>Verify credential state</h3><span>Try a registered, revoked, or unknown ID such as TST-UNKNOWN.</span></div></div><div className="lookup-inner"><div className="lookup-controls"><input aria-label="Credential ID to verify" value={lookup} onChange={e => setLookup(e.target.value.toUpperCase())}/><button className="primary" disabled={busy} onClick={async () => {const result=await act('/registry/lookup',{credential_id:lookup});if(result)setProof(result)}}>Write verification event</button></div>{proof && <div className="lookup-result"><Status value={proof.status}/><span>Document hash: {proof.document_hash_match === null ? 'No document supplied' : proof.document_hash_match ? 'MATCH' : 'MISMATCH'}</span><b className="mono">{proof.transaction_id}</b><small>Event hash {short(proof.event_hash)}</small></div>}</div></section></>
}

function Audit({data}) { if(!data)return <div className="loading">Loading audit trail…</div>;return <><div className="section-head"><div><h2>Hash-linked event trail</h2><p>Each issuance, verification, and revocation references the previous event hash.</p></div><Status value={data.integrity.intact ? 'CHAIN INTACT' : 'CHAIN ISSUE'}/></div><div className="audit-summary"><div><small>EVENTS CHECKED</small><strong>{data.integrity.event_count}</strong></div><div><small>HEAD HASH</small><strong className="mono">{short(data.integrity.head_hash)}</strong></div><div><small>NETWORK</small><strong>Local simulator</strong></div></div><section className="surface"><div className="surface-head"><div><h3>Recent transactions</h3><span>Illustrative authority roles; no consensus nodes are running.</span></div></div><div className="table-wrap"><table><thead><tr><th>Transaction</th><th>Event</th><th>Authority</th><th>Credential</th><th>Status</th><th>Recorded</th></tr></thead><tbody>{data.events.map(event => <tr key={event.transaction_id}><td className="mono">{event.transaction_id}</td><td>{event.event_type}</td><td>{event.authority}</td><td className="mono">{event.credential_id}</td><td><Status value={event.status}/></td><td>{time(event.created_at)}</td></tr>)}</tbody></table></div></section></> }
