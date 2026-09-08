# CAD Check — Automotive Engineering Verification Capability Prototype

A deliberately small MVP for validating whether automotive package-check rules can be expressed as reusable verification cases, executed deterministically, compared across model versions, and reviewed with evidence + trace.

## What this MVP proves

- 3 reusable executor types cover a useful slice of engineering checks: minimum clearance, directional distance, angle/orientation.
- 18 verification cases can be batch-run against a controlled V1/V2 vehicle fixture.
- V1/V2 regression is classified as NEW_FAIL / FIXED / IMPROVED / REGRESSED / UNCHANGED.
- Every result has evidence metadata and a readable trace.
- A single Web Workspace lets an engineer run, filter, inspect and review results.

## What it deliberately does NOT prove

- CATIA → STEP AP242 production fidelity.
- Real OEM part semantic binding across versions.
- Enterprise performance, security, deployment or sign-off.
- Headroom, visibility, dynamic DMU, CAE or AI rule compilation.

## Quick start

Requires Python 3.10+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn server.app:app --reload
```

Open: http://127.0.0.1:8000

Or:

```bash
./start.sh
```

## Run tests

```bash
pytest -q
```

## MVP structure

```text
server/   deterministic verification runtime + API
rules/    hand-authored verification cases
web/      single-page verification workspace
tests/    regression + geometry tests
docs/     product plan and MVP validation notes
```

## Architecture

```text
Controlled Vehicle Fixture V1 / V2
          ↓
Hand-authored Verification Cases
          ↓
3 deterministic executors
          ↓
PASS / FAIL / REVIEW_REQUIRED / BLOCKED
          ↓
V1 ↔ V2 Regression
          ↓
Evidence metadata + Trace
          ↓
Web Verification Workspace
```

The geometry backend is intentionally primitive-based for the first capability prototype. `server/occt_adapter.py` defines the seam for replacing primitive geometry with OCP/OCCT + STEP/XCAF without changing the verification-case or regression contracts.
