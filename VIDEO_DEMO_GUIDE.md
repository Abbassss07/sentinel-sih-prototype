# SENTINEL first-round video guide (target: 2:30)

Record the browser at 1080p if possible. Keep the pointer deliberate and zoom until the document, transaction proof, and report button are legible. Use only fictional cases. Do not imply seeded components are live AI.

| Time | Show on screen | Suggested narration |
|---|---|---|
| 0:00–0:15 | Overview and Today / This week / This month selector | “SENTINEL is an officer-guided identity screening workflow. It combines document consistency, person checks, and a permissioned-registry design, then records a human decision.” |
| 0:15–0:38 | Choose Edited document; run MRZ checks | “The MRZ check digits are valid, but the visible birth date differs from the MRZ. A checksum alone does not prove a document was unaltered.” |
| 0:38–0:58 | Liveness and face screens | “This first-round prototype uses a guided challenge and seeded face outcome. We label these simulations; camera analysis and model inference are not claimed here.” |
| 0:58–1:30 | Verify credential; pause on transaction, hash mismatch, issuer and status | “We hash the presented fields and compare them with the issuer’s record. The credential is valid, yet the presented hash differs. A verification transaction is appended to a hash-linked local audit trail.” |
| 1:30–1:52 | Decision step; show reasons, choose HOLD or ESCALATE | “Risk points come from explicit rules, not an opaque confidence score. The officer—not the software—takes the final action.” |
| 1:52–2:08 | Generate final report and show PDF | “Only after the decision, the system stores an auditable PDF with checks, reasons, action, and ledger proof.” |
| 2:08–2:30 | Credential registry, lookup, audit trail | “Issuance, verification and revocation are visible as linked events. This local registry is a prototype for a multi-authority Fabric deployment, not a Fabric network today.” |

If time remains, briefly open Wrong person: its document and issuer hash match, but the seeded person check calls for a hold. This makes the “valid document ≠ right traveller” point.

## Before recording

1. Run backend and frontend using the README instructions.
2. Confirm the dashboard shows “Local ledger simulator” and the audit trail says “Hash chain intact.”
3. Practice the edited-document flow once; create a fresh case for the recording.
4. Keep synthetic/test notices visible.
5. Do not call the local simulator “Hyperledger Fabric,” the guided challenge “MediaPipe,” or the seeded face result “AI confidence.” Those are planned integrations.

## Judge questions

- **Why a ledger?** If multiple authorised agencies issue, verify and revoke credentials, they need shared provenance and tamper-evident state. A single-agency deployment could use a simpler signed database.
- **What runs today?** React/FastAPI/SQLite, MRZ checks, SHA-256 credential comparison, a persisted hash-linked test registry, deterministic rules, audit history, and saved PDFs.
- **What is simulated?** OCR input, camera liveness, face-model outcome, and Fabric consensus.
- **What is kept off-chain?** Raw passport imagery and biometrics. The registry holds credential digests, status, issuer, and event metadata.
