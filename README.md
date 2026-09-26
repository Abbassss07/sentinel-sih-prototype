# SENTINEL — SIH26188 first-round prototype

SENTINEL is a **synthetic/test-data-only** identity and document screening walkthrough for a 2–3 minute first-round submission video. It is not an operational border-control system. The interface separates real code paths from simulated components.

## What the prototype shows

- React officer console with Today, This week, and This month activity filters.
- Three fictional cases: genuine credential, edited-document mismatch, valid document presented by the wrong test person.
- Guided document → liveness → face → ledger → decision flow.
- TD3-like MRZ check-digit validation and visible-field cross-checks running in Python.
- SQLite-backed credential registry with SHA-256 hashes, VALID / REVOKED / NOT_FOUND states, issuance/revocation, transaction IDs, and hash-linked audit events.
- Deterministic risk points and reasons, an explicit officer decision, and a separate Generate final report action.
- PDF reports stored in SQLite, hashed, audited, and downloadable.

The edited-document case is the central demonstration: its MRZ has internally valid check digits, but the visible date of birth differs from the MRZ and the presented credential hash differs from the issuer record.

## Run locally

Requirements: Python 3.11+ and Node.js 20+. In two terminals:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1
```

Open http://127.0.0.1:5173. Vite proxies `/api` to FastAPI. SQLite data is created in `backend/sentinel.db` on first startup; the file is ignored by Git. Run `npm run build` in `frontend` to check the production bundle.

See [VIDEO_DEMO_GUIDE.md](VIDEO_DEMO_GUIDE.md) for a timed recording path and accurate narration.

## Architecture and accuracy

```text
React officer console
        ↓
FastAPI case/check API
        ├── SQLite cases, checks, audit, and stored PDF
        ├── TD3-like MRZ parser and deterministic rule engine
        └── Local hash-linked credential registry
```

The registry is a **simulator, not Hyperledger Fabric**. Events are persisted, linked to prior event hashes, and checked for integrity. Issuer/checkpoint/review-authority names are illustrative roles in one local process, not independent nodes or consensus. No raw passport image or biometric template is stored in the registry.

OCR fields are seeded; there is no image upload or EasyOCR inference yet. The challenge-response UI does not use a camera or MediaPipe. The face outcome is seeded; no ONNX model runs. These technologies are the intended next stage, alongside a real permissioned Fabric deployment. The UI and PDF disclose the same limitations. Rule points are **not confidence scores**; the officer makes the final action.

## Report lifecycle

After all checks, the officer records CLEAR, ESCALATE, or HOLD. Only then does Generate final report become available. It renders saved checks, proof, reasons, action, and audit history into a PDF BLOB in SQLite. Repeating generation returns the existing PDF instead of changing it.

Use only fictional cases. Do not enter real identity or biometric data.
