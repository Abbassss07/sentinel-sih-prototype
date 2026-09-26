"""Local, hash-linked credential registry used for the video demonstration.

This is not Hyperledger Fabric and makes no consensus or multi-node claim.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import UTC, datetime

ADAPTER_NAME = "Local hash-linked ledger simulator"
GENESIS_HASH = "0" * 64


def now() -> str:
    return datetime.now(UTC).isoformat()


def credential_hash(credential_id: str, holder_name: str, date_of_birth: str) -> str:
    canonical = f"{credential_id.strip().upper()}|{holder_name.strip().upper()}|{date_of_birth.strip()}"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def initialise(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS registry_credentials (
            credential_id TEXT PRIMARY KEY,
            issuer TEXT NOT NULL,
            credential_hash TEXT NOT NULL,
            status TEXT NOT NULL,
            issued_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS registry_events (
            transaction_id TEXT PRIMARY KEY,
            credential_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            authority TEXT NOT NULL,
            status TEXT NOT NULL,
            document_hash_match INTEGER,
            payload_digest TEXT NOT NULL,
            previous_hash TEXT NOT NULL,
            event_hash TEXT NOT NULL,
            case_id TEXT,
            created_at TEXT NOT NULL
        );
        """
    )
    seeds = (
        ("TST-0042", "Ananya Rao", "1994-08-17"),
        ("TST-0097", "Vikram Sen", "1988-02-02"),
        ("TST-0200", "Mira Das", "1991-11-06"),
    )
    for credential_id, holder, birth_date in seeds:
        if connection.execute("SELECT 1 FROM registry_credentials WHERE credential_id = ?", (credential_id,)).fetchone() is None:
            register(connection, credential_id, holder, birth_date, "Test Passport Authority")


def _event_material(event: dict) -> bytes:
    keys = ("transaction_id", "credential_id", "event_type", "authority", "status", "document_hash_match", "payload_digest", "previous_hash", "case_id", "created_at")
    return json.dumps({key: event.get(key) for key in keys}, sort_keys=True, separators=(",", ":")).encode("utf-8")


def append_event(connection: sqlite3.Connection, credential_id: str, event_type: str, authority: str, status: str, payload_digest: str, document_hash_match: bool | None = None, case_id: str | None = None) -> dict:
    previous = connection.execute("SELECT event_hash FROM registry_events ORDER BY rowid DESC LIMIT 1").fetchone()
    event = {
        "transaction_id": "TX-" + uuid.uuid4().hex[:16].upper(),
        "credential_id": credential_id,
        "event_type": event_type,
        "authority": authority,
        "status": status,
        "document_hash_match": None if document_hash_match is None else int(document_hash_match),
        "payload_digest": payload_digest,
        "previous_hash": previous["event_hash"] if previous else GENESIS_HASH,
        "case_id": case_id,
        "created_at": now(),
    }
    event["event_hash"] = hashlib.sha256(_event_material(event)).hexdigest()
    connection.execute(
        """INSERT INTO registry_events
        (transaction_id, credential_id, event_type, authority, status, document_hash_match, payload_digest, previous_hash, event_hash, case_id, created_at)
        VALUES (:transaction_id, :credential_id, :event_type, :authority, :status, :document_hash_match, :payload_digest, :previous_hash, :event_hash, :case_id, :created_at)""",
        event,
    )
    return event


def register(connection: sqlite3.Connection, credential_id: str, holder_name: str, date_of_birth: str, issuer: str) -> dict:
    credential_id = credential_id.strip().upper()
    if connection.execute("SELECT 1 FROM registry_credentials WHERE credential_id = ?", (credential_id,)).fetchone():
        raise ValueError("Credential already registered")
    digest = credential_hash(credential_id, holder_name, date_of_birth)
    timestamp = now()
    connection.execute(
        "INSERT INTO registry_credentials (credential_id, issuer, credential_hash, status, issued_at, updated_at) VALUES (?, ?, ?, 'VALID', ?, ?)",
        (credential_id, issuer, digest, timestamp, timestamp),
    )
    event = append_event(connection, credential_id, "REGISTER", issuer, "VALID", digest)
    return {"credential_id": credential_id, "status": "VALID", "issuer": issuer, "credential_hash": digest, **event}


def revoke(connection: sqlite3.Connection, credential_id: str, authority: str) -> dict:
    credential_id = credential_id.strip().upper()
    row = connection.execute("SELECT * FROM registry_credentials WHERE credential_id = ?", (credential_id,)).fetchone()
    if row is None:
        raise LookupError("Credential not found")
    if row["status"] == "REVOKED":
        raise ValueError("Credential is already revoked")
    connection.execute("UPDATE registry_credentials SET status = 'REVOKED', updated_at = ? WHERE credential_id = ?", (now(), credential_id))
    return append_event(connection, credential_id, "REVOKE", authority, "REVOKED", row["credential_hash"])


def verify(connection: sqlite3.Connection, credential_id: str, presented_hash: str | None, case_id: str | None = None) -> dict:
    credential_id = credential_id.strip().upper()
    row = connection.execute("SELECT * FROM registry_credentials WHERE credential_id = ?", (credential_id,)).fetchone()
    status = row["status"] if row else "NOT_FOUND"
    match = (presented_hash == row["credential_hash"]) if row and presented_hash else None
    event = append_event(
        connection,
        credential_id,
        "VERIFY",
        "Border Checkpoint (test)",
        status,
        presented_hash or hashlib.sha256(credential_id.encode()).hexdigest(),
        match,
        case_id,
    )
    return {
        "adapter": ADAPTER_NAME,
        "credential_id": credential_id,
        "issuer": row["issuer"] if row else None,
        "status": status,
        "document_hash_match": match,
        "credential_hash": row["credential_hash"] if row else None,
        "presented_hash": presented_hash,
        "transaction_id": event["transaction_id"],
        "recorded_at": event["created_at"],
        "event_hash": event["event_hash"],
        "previous_hash": event["previous_hash"],
    }


def chain_integrity(connection: sqlite3.Connection) -> dict:
    previous = GENESIS_HASH
    count = 0
    for row in connection.execute("SELECT * FROM registry_events ORDER BY rowid"):
        event = dict(row)
        if event["previous_hash"] != previous or hashlib.sha256(_event_material(event)).hexdigest() != event["event_hash"]:
            return {"intact": False, "event_count": count, "failed_transaction": event["transaction_id"]}
        previous = event["event_hash"]
        count += 1
    return {"intact": True, "event_count": count, "head_hash": previous}
