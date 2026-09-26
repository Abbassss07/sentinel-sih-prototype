from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

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


def credential_hash(credential_id: str, holder: str, date_of_birth: str) -> str:
    material = f"{credential_id}|{holder}|{date_of_birth}".encode()
    return hashlib.sha256(material).hexdigest()


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


class LedgerProof(BaseModel):
    adapter: str
    credential_id: str
    status: Literal["VALID", "REVOKED", "NOT_FOUND"]
    document_hash_match: bool
    transaction_id: str | None = None
    recorded_at: str | None = None


class Scenario(BaseModel):
    key: str
    title: str
    description: str
    credential_id: str
    holder_name: str
    date_of_birth: str
    document_checks: list[str]
    liveness_checks: list[str]
    face_check: str
    risk_reasons: list[str]
    risk_level: Literal["CLEAR", "REVIEW", "HOLD"]
    ledger: LedgerProof


class CaseAction(BaseModel):
    action: Literal["CLEAR", "ESCALATE", "HOLD"]
    note: str = Field(default="", max_length=1000)


class NewCase(BaseModel):
    scenario_key: str
    checkpoint: str = Field(default="North Terminal · Gate 3", max_length=100)


class LocalLedgerAdapter:
    """Development adapter. Replace with Fabric client without changing API contracts."""

    name = "Local permissioned-ledger simulator"

    def proof_for(self, scenario_key: str) -> LedgerProof:
        scenario = SCENARIOS[scenario_key]
        return scenario.ledger


def proof_for(credential_id: str, status: str, document_hash_match: bool) -> LedgerProof:
    transaction_source = f"{credential_id}:{status}:{document_hash_match}".encode()
    transaction_id = "TX-" + hashlib.sha256(transaction_source).hexdigest()[:16].upper()
    return LedgerProof(
        adapter="Local permissioned-ledger simulator",
        credential_id=credential_id,
        status=status,  # type: ignore[arg-type]
        document_hash_match=document_hash_match,
        transaction_id=transaction_id,
        recorded_at="2026-09-26T08:57:00+00:00",
    )


SCENARIOS: dict[str, Scenario] = {
    "genuine": Scenario(
        key="genuine",
        title="Genuine credential / matching traveller",
        description="Seeded synthetic credential with consistent document data and matching reference person.",
        credential_id="TST-0042",
        holder_name="Ananya Rao",
        date_of_birth="1994-08-17",
        document_checks=["OCR fields extracted", "MRZ-like fields are structurally valid", "Document fields are consistent"],
        liveness_checks=["Face detected", "Turn-left challenge completed", "Live capture recorded"],
        face_check="Reference person and live capture are consistent",
        risk_reasons=["No document-integrity issue identified", "Credential is valid on the test ledger", "Face reference is consistent with live capture"],
        risk_level="CLEAR",
        ledger=proof_for("TST-0042", "VALID", True),
    ),
    "edited_document": Scenario(
        key="edited_document",
        title="Edited document / credential mismatch",
        description="Seeded synthetic case where presented document fields differ from the authority-issued credential hash.",
        credential_id="TST-0042",
        holder_name="Ananya Rao",
        date_of_birth="1994-08-17",
        document_checks=["OCR fields extracted", "MRZ-like fields are structurally valid", "Cross-field document data differs from issued record"],
        liveness_checks=["Face detected", "Turn-left challenge completed", "Live capture recorded"],
        face_check="Reference person and live capture are consistent",
        risk_reasons=["Presented document hash does not match authority-issued credential", "Cross-field consistency check requires officer review", "Ledger credential state itself remains valid"],
        risk_level="REVIEW",
        ledger=proof_for("TST-0042", "VALID", False),
    ),
    "wrong_person": Scenario(
        key="wrong_person",
        title="Genuine credential / wrong person",
        description="Seeded synthetic case where the credential is valid but the live traveller is inconsistent with its reference person.",
        credential_id="TST-0097",
        holder_name="Vikram Sen",
        date_of_birth="1988-02-02",
        document_checks=["OCR fields extracted", "MRZ-like fields are structurally valid", "Document fields are consistent"],
        liveness_checks=["Face detected", "Turn-left challenge completed", "Live capture recorded"],
        face_check="Live capture is inconsistent with credential reference person",
        risk_reasons=["Credential is valid and document hash matches", "Live traveller is inconsistent with credential reference", "Officer escalation is required"],
        risk_level="HOLD",
        ledger=proof_for("TST-0097", "VALID", True),
    ),
}
ledger = LocalLedgerAdapter()


def audit(case_id: str, event_type: str, description: str) -> None:
    with db() as connection:
        connection.execute(
            "INSERT INTO audit_events (id, case_id, event_type, description, created_at) VALUES (?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), case_id, event_type, description, utc_now()),
        )


@app.on_event("startup")
def startup() -> None:
    initialise_database()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "environment": "synthetic-test-prototype"}


@app.get("/api/scenarios", response_model=list[Scenario])
def list_scenarios() -> list[Scenario]:
    return list(SCENARIOS.values())


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
    if row is None:
        raise HTTPException(status_code=404, detail="Case not found")
    scenario = SCENARIOS[row["scenario_key"]]
    return {"case": dict(row), "scenario": scenario.model_dump(), "audit": [dict(event) for event in events]}


@app.get("/api/cases/{case_id}/ledger-proof", response_model=LedgerProof)
def verify_ledger(case_id: str) -> LedgerProof:
    with db() as connection:
        row = connection.execute("SELECT scenario_key FROM cases WHERE id = ?", (case_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Case not found")
    result = ledger.proof_for(row["scenario_key"])
    with db() as connection:
        connection.execute(
            "INSERT INTO ledger_checks (id, case_id, proof_json, verified_at) VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), case_id, result.model_dump_json(), utc_now()),
        )
    audit(case_id, "ledger_verified", f"Ledger status {result.status}; document hash match: {result.document_hash_match}")
    return result


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
        report_id = f"RPT-{uuid.uuid4().hex[:12].upper()}"
        generated_at = utc_now()
        proof = {**json.loads(proof_row["proof_json"]), "verified_at": proof_row["verified_at"]}
        pdf = build_report(dict(case_row), SCENARIOS[case_row["scenario_key"]].model_dump(), proof, [dict(event) for event in events], report_id, generated_at)
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
