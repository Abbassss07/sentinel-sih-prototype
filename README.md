# SENTINEL — Prototype

SENTINEL is a local prototype for AI-assisted identity and document screening. It is designed for **synthetic/test data only** and is not a production identity, biometric, or border-control system.

## What this first milestone contains

- A React officer console with the approved guided screening flow.
- Three seeded test scenarios: credential clear, edited-document mismatch, and wrong-person.
- A FastAPI API and SQLite case/audit store.
- Seeded, explainable test findings—no confidence percentages or automated decisions.
- A separate **Generate final report** action after the officer decision. The PDF is stored as a BLOB in SQLite, with a SHA-256 digest and audit event, and can be downloaded from the case.

## Run locally

Start the API in one terminal:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Start the web app in another:

```bash
cd frontend
npm install
npm run dev
```

Open the local address printed by Vite. The frontend proxies `/api` requests to FastAPI.

## Architecture at this stage

```text
React officer console → FastAPI screening API → SQLite (cases + audit events)
                                      ↓
                         Ledger adapter interface (mock initially)
```

The current local ledger simulator returns a seeded credential status, document-hash match result, and proof identifier. A real credential registry and Hyperledger Fabric adapter are later milestones. The simulator is labeled in both the interface and report. It never stores document images or biometric data.

## Prototype limitations

OCR, liveness, and face matching screens currently model the agreed test-case outcomes. In the next milestones they will be connected to EasyOCR/OpenCV, MediaPipe, and an ONNX-compatible face-verification pipeline. The officer remains the decision-maker in all flows.

## Report lifecycle

The officer must run the ledger check, record a final action, then click **Generate final report**. The API builds a PDF from the case record, seeded screening findings, latest ledger check, and saved audit events. It stores the PDF bytes in SQLite. A second generation request returns the existing report rather than changing it. The download endpoint returns that saved PDF.
