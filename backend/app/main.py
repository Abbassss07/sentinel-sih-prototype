from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

from . import ledger as registry
from .document import synthetic_document
from .report import build_report

APP_DIR = Path(__file__).resolve().parent
DATABASE_PATH = APP_DIR.parent / "sentinel.db"

app = FastAPI(title="SENTINEL Prototype API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


@contextmanager
def db():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def initialise_database() -> None:
    with db() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS cases (
                id TEXT PRIMARY KEY,
                scenario_key TEXT NOT NULL,
                checkpoint TEXT NOT NULL,
                status TEXT NOT NULL,
                officer_action TEXT,
                officer_note TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit_events (
                id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                description TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(case_id) REFERENCES cases(id)
            );
            CREATE TABLE IF NOT EXISTS ledger_checks (
                id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                proof_json TEXT NOT NULL,
                verified_at TEXT NOT NULL,
                FOREIGN KEY(case_id) REFERENCES cases(id)
            );
            CREATE TABLE IF NOT EXISTS screening_checks (
                case_id TEXT NOT NULL,
                check_type TEXT NOT NULL,
                result_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (case_id, check_type),
                FOREIGN KEY(case_id) REFERENCES cases(id)
            );
            CREATE TABLE IF NOT EXISTS reports (
                id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL UNIQUE,
                pdf BLOB NOT NULL,
                sha256 TEXT NOT NULL,
                generated_at TEXT NOT NULL,
                FOREIGN KEY(case_id) REFERENCES cases(id)
            );
            """
        )
        registry.initialise(connection)
        if connection.execute("SELECT COUNT(*) FROM cases WHERE id LIKE 'DEMO-%'").fetchone()[0] == 0:
            for index, key in enumerate(("genuine", "edited_document", "wrong_person"), start=1):
                scenario = SCENARIOS[key]
                case_id = f"DEMO-{index:04d}"
                timestamp = (datetime.now(UTC) - timedelta(minutes=8 * index)).isoformat()
                connection.execute(
                    "INSERT OR IGNORE INTO cases (id, scenario_key, checkpoint, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (case_id, key, "North Terminal · Gate 3", "DEMO_SAMPLE", timestamp, timestamp),
                )
                document = scenario.document
                presented_hash = registry.credential_hash(scenario.credential_id, scenario.holder_name, document["date_of_birth"])
                proof = registry.verify(connection, scenario.credential_id, presented_hash, case_id)
                connection.execute(
                    "INSERT INTO ledger_checks (id, case_id, proof_json, verified_at) VALUES (?, ?, ?, ?)",
                    (str(uuid.uuid4()), case_id, json.dumps(proof), timestamp),
                )


class LedgerProof(BaseModel):
    adapter: str
    credential_id: str
    status: Literal["VALID", "REVOKED", "NOT_FOUND"]
    document_hash_match: bool | None
    issuer: str | None = None
    credential_hash: str | None = None
    presented_hash: str | None = None
    transaction_id: str | None = None
    recorded_at: str | None = None
    event_hash: str | None = None
    previous_hash: str | None = None


class Scenario(BaseModel):
    key: str
    title: str
    description: str
    credential_id: str
    holder_name: str
    date_of_birth: str
    document: dict
    document_checks: list[str]
    liveness_checks: list[str]
    face_check: str
    risk_reasons: list[str]
    risk_level: Literal["CLEAR", "REVIEW", "HOLD"]


class CaseAction(BaseModel):
    action: Literal["CLEAR", "ESCALATE", "HOLD"]
    note: str = Field(default="", max_length=1000)


class NewCase(BaseModel):
    scenario_key: str
    checkpoint: str = Field(default="North Terminal · Gate 3", max_length=100)


class NewCredential(BaseModel):
    credential_id: str = Field(pattern=r"^(TST|DEMO)-[A-Za-z0-9-]{3,24}$")
    holder_name: str = Field(min_length=2, max_length=80)
    date_of_birth: str


class RegistryLookup(BaseModel):
    credential_id: str = Field(min_length=3, max_length=40)


class LivenessChallenge(BaseModel):
    turned_left: bool
    returned_center: bool


SCENARIOS: dict[str, Scenario] = {
    "genuine": Scenario(
        key="genuine",
        title="Genuine credential / matching traveller",
        description="Seeded synthetic credential with consistent document data and matching reference person.",
        credential_id="TST-0042",
        holder_name="Ananya Rao",
        date_of_birth="1994-08-17",
        document=synthetic_document("TST-0042", "Ananya Rao", "1994-08-17", "2030-01-01"),
        document_checks=["Seeded OCR fields loaded", "TD3 MRZ checksums valid", "Visible fields match MRZ"],
        liveness_checks=["Face detected", "Turn-left challenge completed", "Live capture recorded"],
        face_check="Reference person and live capture are consistent",
        risk_reasons=["No document-integrity issue identified", "Credential is valid on the test ledger", "Face reference is consistent with live capture"],
        risk_level="CLEAR",
    ),
    "edited_document": Scenario(
        key="edited_document",
        title="Edited document / credential mismatch",
        description="Seeded synthetic case where presented document fields differ from the authority-issued credential hash.",
        credential_id="TST-0042",
        holder_name="Ananya Rao",
        date_of_birth="1994-08-17",
        document=synthetic_document("TST-0042", "Ananya Rao", "1994-08-17", "2030-01-01", presented_birth_date="1994-08-19"),
        document_checks=["Seeded OCR fields loaded", "TD3 MRZ checksums valid", "Visible date of birth differs from MRZ"],
        liveness_checks=["Face detected", "Turn-left challenge completed", "Live capture recorded"],
        face_check="Reference person and live capture are consistent",
        risk_reasons=["Presented document hash does not match authority-issued credential", "Cross-field consistency check requires officer review", "Ledger credential state itself remains valid"],
        risk_level="REVIEW",
    ),
    "wrong_person": Scenario(
        key="wrong_person",
        title="Genuine credential / wrong person",
        description="Seeded synthetic case where the credential is valid but the live traveller is inconsistent with its reference person.",
        credential_id="TST-0097",
        holder_name="Vikram Sen",
        date_of_birth="1988-02-02",
        document=synthetic_document("TST-0097", "Vikram Sen", "1988-02-02", "2030-01-01"),
        document_checks=["Seeded OCR fields loaded", "TD3 MRZ checksums valid", "Visible fields match MRZ"],
        liveness_checks=["Face detected", "Turn-left challenge completed", "Live capture recorded"],
        face_check="Live capture is inconsistent with credential reference person",
        risk_reasons=["Credential is valid and document hash matches", "Live traveller is inconsistent with credential reference", "Officer escalation is required"],
        risk_level="HOLD",
    ),
}


def audit(case_id: str, event_type: str, description: str) -> None:
    with db() as connection:
        connection.execute(
            "INSERT INTO audit_events (id, case_id, event_type, description, created_at) VALUES (?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), case_id, event_type, description, utc_now()),
        )


def save_check(case_id: str, check_type: str, result: dict, description: str) -> dict:
    with db() as connection:
        row = connection.execute("SELECT status FROM cases WHERE id = ?", (case_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Case not found")
        if row["status"] != "IN_PROGRESS":
            raise HTTPException(status_code=409, detail="Case is no longer in progress")
        connection.execute(
            "INSERT OR REPLACE INTO screening_checks (case_id, check_type, result_json, created_at) VALUES (?, ?, ?, ?)",
            (case_id, check_type, json.dumps(result), utc_now()),
        )
    audit(case_id, check_type, description)
    return result


def calculate_risk(scenario: Scenario, proof: dict) -> dict:
    points = 0
    reasons = []
    if not scenario.document["mrz"]["checksums_valid"]:
        points += 40
        reasons.append("MRZ checksum validation failed (+40)")
    if not scenario.document["mrz"]["cross_field_match"]:
        points += 25
        reasons.append("Visible document fields differ from MRZ (+25)")
    if proof["document_hash_match"] is False:
        points += 45
        reasons.append("Presented document hash differs from issuer record (+45)")
    if scenario.key == "wrong_person":
        points += 60
        reasons.append("Live person differs from reference (hold condition, +60)")
    if proof["status"] == "REVOKED":
        points += 90
        reasons.append("Credential has been revoked (hold condition, +90)")
    elif proof["status"] == "NOT_FOUND":
        points += 70
        reasons.append("Credential not found in the test registry (hold condition, +70)")
    if not reasons:
        reasons.append("MRZ and visible fields agree; credential hash and live person are consistent")
    hard_stop = scenario.key == "wrong_person" or proof["status"] in ("REVOKED", "NOT_FOUND")
    level = "HOLD" if hard_stop else "REVIEW" if points else "CLEAR"
    return {"points": min(points, 100), "level": level, "reasons": reasons, "method": "Deterministic prototype rules; points are not model confidence"}


@app.on_event("startup")
def startup() -> None:
    initialise_database()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "environment": "synthetic-test-prototype"}


@app.get("/api/scenarios", response_model=list[Scenario])
def list_scenarios() -> list[Scenario]:
    return list(SCENARIOS.values())


@app.get("/api/overview")
def overview(period: Literal["today", "week", "month"] = "today") -> dict:
    current = datetime.now(UTC)
    cutoff = {
        "today": current.replace(hour=0, minute=0, second=0, microsecond=0),
        "week": (current - timedelta(days=current.weekday())).replace(hour=0, minute=0, second=0, microsecond=0),
        "month": current.replace(day=1, hour=0, minute=0, second=0, microsecond=0),
    }[period].isoformat()
    with db() as connection:
        rows = connection.execute("SELECT id, scenario_key, checkpoint, status, created_at FROM cases WHERE created_at >= ? ORDER BY created_at DESC", (cutoff,)).fetchall()
        checks = connection.execute("SELECT COUNT(*) FROM ledger_checks WHERE verified_at >= ?", (cutoff,)).fetchone()[0]
        events = connection.execute("SELECT transaction_id, credential_id, event_type, authority, status, created_at FROM registry_events ORDER BY rowid DESC LIMIT 4").fetchall()
        integrity = registry.chain_integrity(connection)
    cases = [{**dict(row), "title": SCENARIOS[row["scenario_key"]].title, "suggested_level": SCENARIOS[row["scenario_key"]].risk_level} for row in rows]
    return {
        "period": period,
        "screenings": len(cases),
        "ledger_checks": checks,
        "attention": sum(case["suggested_level"] != "CLEAR" for case in cases),
        "recent_cases": cases[:5],
        "recent_events": [dict(event) for event in events],
        "chain": integrity,
    }


@app.get("/api/registry")
def list_registry() -> dict:
    with db() as connection:
        credentials = connection.execute("SELECT * FROM registry_credentials ORDER BY credential_id").fetchall()
        events = connection.execute("SELECT transaction_id, credential_id, event_type, authority, status, event_hash, previous_hash, created_at FROM registry_events ORDER BY rowid DESC LIMIT 30").fetchall()
        integrity = registry.chain_integrity(connection)
    return {"adapter": registry.ADAPTER_NAME, "credentials": [dict(row) for row in credentials], "events": [dict(row) for row in events], "integrity": integrity}


@app.post("/api/registry")
def register_credential(payload: NewCredential) -> dict:
    try:
        datetime.fromisoformat(payload.date_of_birth)
        with db() as connection:
            result = registry.register(connection, payload.credential_id, payload.holder_name, payload.date_of_birth, "Test Passport Authority")
        return result
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/registry/lookup", response_model=LedgerProof)
def registry_lookup(payload: RegistryLookup) -> LedgerProof:
    with db() as connection:
        result = registry.verify(connection, payload.credential_id, None)
    return LedgerProof(**result)


@app.post("/api/registry/{credential_id}/revoke")
def revoke_credential(credential_id: str) -> dict:
    if credential_id in ("TST-0042", "TST-0097"):
        raise HTTPException(status_code=409, detail="Core screening fixtures are reserved; revoke a newly registered test credential or TST-0200")
    try:
        with db() as connection:
            result = registry.revoke(connection, credential_id, "Immigration Review (test)")
        return result
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/cases")
def create_case(payload: NewCase) -> dict[str, str]:
    if payload.scenario_key not in SCENARIOS:
        raise HTTPException(status_code=404, detail="Unknown seeded scenario")
    case_id = f"SCR-{datetime.now().strftime('%Y')}-{uuid.uuid4().hex[:4].upper()}"
    timestamp = utc_now()
    with db() as connection:
        connection.execute(
            "INSERT INTO cases (id, scenario_key, checkpoint, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (case_id, payload.scenario_key, payload.checkpoint, "IN_PROGRESS", timestamp, timestamp),
        )
    audit(case_id, "case_opened", f"Synthetic test case opened: {SCENARIOS[payload.scenario_key].title}")
    return {"case_id": case_id}


@app.get("/api/cases/{case_id}")
def get_case(case_id: str) -> dict:
    with db() as connection:
        row = connection.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
        events = connection.execute(
            "SELECT id, event_type, description, created_at FROM audit_events WHERE case_id = ? ORDER BY created_at", (case_id,)
        ).fetchall()
        proof_row = connection.execute("SELECT proof_json FROM ledger_checks WHERE case_id = ? ORDER BY verified_at DESC LIMIT 1", (case_id,)).fetchone()
        report_row = connection.execute("SELECT id, sha256, generated_at FROM reports WHERE case_id = ?", (case_id,)).fetchone()
        checks = connection.execute("SELECT check_type, result_json FROM screening_checks WHERE case_id = ?", (case_id,)).fetchall()
    if row is None:
        raise HTTPException(status_code=404, detail="Case not found")
    scenario = SCENARIOS[row["scenario_key"]]
    proof = json.loads(proof_row["proof_json"]) if proof_row else None
    return {"case": dict(row), "scenario": scenario.model_dump(), "checks": {check["check_type"]: json.loads(check["result_json"]) for check in checks}, "ledger": proof, "risk": calculate_risk(scenario, proof) if proof else None, "report": {**dict(report_row), "download_url": f"/api/cases/{case_id}/report.pdf"} if report_row else None, "audit": [dict(event) for event in events]}


@app.post("/api/cases/{case_id}/document-check")
def check_document(case_id: str) -> dict:
    with db() as connection:
        row = connection.execute("SELECT scenario_key FROM cases WHERE id = ?", (case_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Case not found")
    document = SCENARIOS[row["scenario_key"]].document
    result = {"source": "seeded synthetic fields", "mrz": document["mrz"], "visible_fields": {key: document[key] for key in ("passport_number", "holder_name", "date_of_birth", "expiry_date")}}
    return save_check(case_id, "document_check", result, f"TD3 checksum valid: {document['mrz']['checksums_valid']}; visible/MRZ fields match: {document['mrz']['cross_field_match']}")


@app.post("/api/cases/{case_id}/liveness")
def check_liveness(case_id: str, payload: LivenessChallenge) -> dict:
    if not payload.turned_left or not payload.returned_center:
        raise HTTPException(status_code=422, detail="Complete both challenge steps")
    result = {"source": "guided demo simulation", "challenge": "turn left, return to centre", "completed": True, "camera_analysis": False}
    return save_check(case_id, "liveness", result, "Guided demo liveness challenge completed; no camera analysis")


@app.post("/api/cases/{case_id}/face-check")
def check_face(case_id: str) -> dict:
    with db() as connection:
        row = connection.execute("SELECT scenario_key FROM cases WHERE id = ?", (case_id,)).fetchone()
        liveness = connection.execute("SELECT 1 FROM screening_checks WHERE case_id = ? AND check_type = 'liveness'", (case_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Case not found")
    if liveness is None:
        raise HTTPException(status_code=409, detail="Complete the liveness challenge first")
    match = row["scenario_key"] != "wrong_person"
    result = {"source": "seeded synthetic outcome", "reference_match": match, "model_inference": False}
    return save_check(case_id, "face_check", result, f"Seeded face reference consistency: {match}")


@app.get("/api/cases/{case_id}/ledger-proof", response_model=LedgerProof)
@app.post("/api/cases/{case_id}/ledger-proof", response_model=LedgerProof)
def verify_ledger(case_id: str) -> LedgerProof:
    with db() as connection:
        row = connection.execute("SELECT scenario_key FROM cases WHERE id = ?", (case_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Case not found")
    scenario = SCENARIOS[row["scenario_key"]]
    presented_hash = registry.credential_hash(scenario.credential_id, scenario.holder_name, scenario.document["date_of_birth"])
    with db() as connection:
        result = registry.verify(connection, scenario.credential_id, presented_hash, case_id)
        connection.execute(
            "INSERT INTO ledger_checks (id, case_id, proof_json, verified_at) VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), case_id, json.dumps(result), utc_now()),
        )
    audit(case_id, "ledger_verified", f"Transaction {result['transaction_id']}; status {result['status']}; document hash match: {result['document_hash_match']}")
    return LedgerProof(**result)


@app.get("/api/cases/{case_id}/risk")
def case_risk(case_id: str) -> dict:
    with db() as connection:
        row = connection.execute("SELECT scenario_key FROM cases WHERE id = ?", (case_id,)).fetchone()
        proof = connection.execute("SELECT proof_json FROM ledger_checks WHERE case_id = ? ORDER BY verified_at DESC LIMIT 1", (case_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Case not found")
    if proof is None:
        raise HTTPException(status_code=409, detail="Run credential verification first")
    return calculate_risk(SCENARIOS[row["scenario_key"]], json.loads(proof["proof_json"]))


@app.post("/api/cases/{case_id}/action")
def record_action(case_id: str, payload: CaseAction) -> dict[str, str]:
    with db() as connection:
        row = connection.execute("SELECT status FROM cases WHERE id = ?", (case_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Case not found")
        if row["status"] != "IN_PROGRESS":
            raise HTTPException(status_code=409, detail="Decision has already been recorded")
        proof = connection.execute("SELECT id FROM ledger_checks WHERE case_id = ? LIMIT 1", (case_id,)).fetchone()
        if proof is None:
            raise HTTPException(status_code=409, detail="Verify the credential before recording a decision")
        checks = {row["check_type"] for row in connection.execute("SELECT check_type FROM screening_checks WHERE case_id = ?", (case_id,))}
        if not {"document_check", "liveness", "face_check"}.issubset(checks):
            raise HTTPException(status_code=409, detail="Complete document, liveness, and face checks first")
        cursor = connection.execute(
            "UPDATE cases SET officer_action = ?, officer_note = ?, status = ?, updated_at = ? WHERE id = ?",
            (payload.action, payload.note.strip(), "DECISION_RECORDED", utc_now(), case_id),
        )
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Case not found")
    audit(case_id, "officer_action", f"Officer action recorded: {payload.action}")
    return {"status": "decision_recorded"}


@app.post("/api/cases/{case_id}/report")
def generate_report(case_id: str) -> dict[str, str]:
    with db() as connection:
        case_row = connection.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
        if case_row is None:
            raise HTTPException(status_code=404, detail="Case not found")
        if case_row["status"] not in ("DECISION_RECORDED", "REPORT_GENERATED"):
            raise HTTPException(status_code=409, detail="Record an officer decision first")
        existing = connection.execute("SELECT id, sha256, generated_at FROM reports WHERE case_id = ?", (case_id,)).fetchone()
        if existing is not None:
            return {**dict(existing), "download_url": f"/api/cases/{case_id}/report.pdf"}
        proof_row = connection.execute(
            "SELECT proof_json, verified_at FROM ledger_checks WHERE case_id = ? ORDER BY verified_at DESC LIMIT 1", (case_id,)
        ).fetchone()
        if proof_row is None:
            raise HTTPException(status_code=409, detail="No credential verification is recorded")
        events = connection.execute(
            "SELECT id, event_type, description, created_at FROM audit_events WHERE case_id = ? ORDER BY created_at", (case_id,)
        ).fetchall()
        checks = connection.execute(
            "SELECT check_type, result_json FROM screening_checks WHERE case_id = ?", (case_id,)
        ).fetchall()
        report_id = f"RPT-{uuid.uuid4().hex[:12].upper()}"
        generated_at = utc_now()
        proof = {**json.loads(proof_row["proof_json"]), "verified_at": proof_row["verified_at"]}
        scenario = SCENARIOS[case_row["scenario_key"]].model_dump()
        risk = calculate_risk(SCENARIOS[case_row["scenario_key"]], proof)
        scenario["risk_level"] = risk["level"]
        scenario["risk_reasons"] = risk["reasons"]
        scenario["risk_points"] = risk["points"]
        pdf = build_report(
            dict(case_row), scenario, proof, [dict(event) for event in events],
            {check["check_type"]: json.loads(check["result_json"]) for check in checks},
            report_id, generated_at,
        )
        digest = hashlib.sha256(pdf).hexdigest()
        connection.execute(
            "INSERT INTO reports (id, case_id, pdf, sha256, generated_at) VALUES (?, ?, ?, ?, ?)",
            (report_id, case_id, pdf, digest, generated_at),
        )
        connection.execute("UPDATE cases SET status = ?, updated_at = ? WHERE id = ?", ("REPORT_GENERATED", generated_at, case_id))
    audit(case_id, "report_generated", f"Report {report_id} generated; PDF SHA-256 {digest}")
    return {"id": report_id, "sha256": digest, "generated_at": generated_at, "download_url": f"/api/cases/{case_id}/report.pdf"}


@app.get("/api/cases/{case_id}/report.pdf")
def download_report(case_id: str) -> Response:
    with db() as connection:
        row = connection.execute("SELECT pdf FROM reports WHERE case_id = ?", (case_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Report not generated")
    return Response(
        content=row["pdf"],
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="SENTINEL-{case_id}.pdf"'},
    )
