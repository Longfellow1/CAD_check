# Viewer Xeokit Trial

## Decision

`dev-2` temporarily replaces the Babylon rendering substrate with official `@xeokit/xeokit-sdk` for the Electron MVP viewer trial.

This is a Viewer implementation trial, **not a change to the product architecture**:

```text
Electron Desktop
  ├─ Renderer: xeokit Viewer Adapter
  └─ Runtime Controller
       └─ CAD Worker: Python/OCP/OCCT
            ├─ STEP/AP242
            ├─ Canonical AssemblyTree
            ├─ exact BRep verification
            └─ demand detail derivative
```

## Why

The Babylon prototype proved that the product can decouple Viewer from engineering truth, but the first thin adapter regressed CAD navigation/visual quality and still required us to build too much generic 3D UX ourselves.

xeokit is being tested because its existing framework already provides engineering-oriented navigation, object emphasis, clipping, picking, snapshots and a high-performance `SceneModel` representation with batching/instancing/DTX paths.

## Integration Contract

1. xeokit does **not** read STEP in the product path.
2. Canonical AssemblyTree remains owned by Python/OCP and is the source of occurrence identity.
3. Whole-vehicle Overview is generated from canonical occurrence bbox data.
4. Overview uses one xeokit `SceneModel` with a shared unit-box geometry instanced per occurrence.
5. Exact/display Detail continues to be generated on demand by OCP and admitted under a bounded resident set.
6. Check values, pass/fail, Evidence provenance and Regression never depend on xeokit.
7. Viewer replacement must not change the Check/Evidence/Replay contracts.

## Trial UX

The first xeokit trial must expose without custom camera math:

- native orbit/pan/zoom CameraControl;
- NavCube;
- Fit, ISO, Front, Right and Top presets;
- orthographic/perspective toggle;
- pick → canonical occurrence ID;
- selection emphasis;
- context X-Ray;
- hide/isolate/show all;
- section plane;
- Evidence line/annotation;
- snapshot and Replay view state.

## Automated Gate

The Electron E2E report must explicitly return:

```json
{
  "viewer": "xeokit",
  "representation": "SceneModel DTX proxy + demand detail"
}
```

Ubuntu, macOS and Windows controlled-model Electron E2E must all pass before this trial is handed to local testing.

## Physical Gate

The library is not frozen until the local 295MB Scania test demonstrates:

- useful Overview significantly earlier than the old all-detail route;
- responsive orbit/pan/zoom;
- correct pick → occurrence mapping;
- stable Hide/Isolate;
- FAIL → local Detail → Evidence;
- no progressive memory/interaction collapse over repeated Case switches.

A failed physical Gate means `NO WINNER`; implementation sunk cost is not a reason to freeze xeokit.

## License Boundary

For this trial we use the unmodified official AGPL-3.0 npm package for internal enterprise MVP validation. No xeokit source fork/modification is introduced.

Before any external distribution, supplier/customer installation, SaaS/network-service exposure, or formal closed-source commercial delivery, the project must perform a new license review and obtain a suitable commercial license if required.
