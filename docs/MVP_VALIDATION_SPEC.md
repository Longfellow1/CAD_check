# MVP Validation Spec

## MVP is an experiment, not a launch product
The MVP succeeds when it answers the key unknowns cheaply enough to decide GO / PIVOT / STOP.

## Learning questions
1. Can 15–25 real-style engineering rules collapse into a few reusable executors?
2. Can the deterministic geometry path reliably execute the selected primitives?
3. Does V1→V2 regression classification make engineering sense?
4. Are Evidence + Trace enough for an engineer to understand a result without reproducing the measurement manually?
5. Is the demo credible enough that an engineering owner is willing to provide real vehicle data for an enterprise pilot?

## MVP scope
- Controlled V1/V2 vehicle fixture.
- 18 hand-authored sanitized verification cases.
- 3 executors: minimum clearance, directional distance, angle.
- Batch execution.
- PASS / FAIL / REVIEW_REQUIRED / BLOCKED.
- Regression: NEW_FAIL / FIXED / IMPROVED / REGRESSED / UNCHANGED / NON_COMPARABLE.
- Evidence metadata + simple 3D workspace + trace.
- Thin Accept review action.

## Explicitly out of scope
- AI rule compiler.
- Automatic semantic binding.
- CATIA AP242 fidelity claims.
- Enterprise identity, permissions, workflow, queue or observability stack.
- Headroom, visibility, DMU motion, CAE.
- Production-grade viewer/performance.

## Success signal
Primary conversion: a package/DMU engineering owner says, “If this can run against a real vehicle node, I am willing to give it a dataset for a pilot.”
