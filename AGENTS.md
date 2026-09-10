# CAD Check Development Contract

## Non-negotiable product form

1. CAD Check MVP is an **Electron Desktop Application**.
2. Electron is the only product entry and acceptance surface.
3. `web/` is Electron Renderer source, not a standalone Web product.
4. FastAPI is an Electron-internal localhost sidecar.
5. Standalone browser mode is debug-only. It cannot satisfy Demo, UX, platform, Viewer, or MVP acceptance.
6. A feature that only works in a browser is **NOT DONE**.
7. `./start.sh` and `start.cmd` must launch Electron, never standalone Uvicorn.
8. Product changes must preserve Python/OCP as engineering truth and keep Viewer replaceable.

Before marking any task complete, verify the corresponding path inside Electron on the target platform.
