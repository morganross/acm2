# ACM 2.0 Step 13: Deployment and Packaging Plan

> **Platform:** Windows, Linux, macOS. Python + SQLite. No Docker.

## Goals
- Distribute ACM 2.0 as a standard Python package (`pip install acm2`).
- Single command `acm2 serve` starts the backend and serves the Web GUI.
- No external dependencies (Node.js is only for building, not running).
- No Docker, no system services.

## 1. Package Configuration (`pyproject.toml`)
- [ ] Define build system (setuptools/hatch/poetry).
- [ ] Define dependencies (fastapi, uvicorn, sqlalchemy, typer, rich, etc.).
- [ ] Define entry point: `acm2 = acm2.cli:app`.
- [ ] Configure package data to include built UI assets.

## 2. Frontend Integration
- [ ] Build React UI (`npm run build` in `ui/`).
- [ ] Output directory should be captured by Python package (e.g., `acm2/app/static`).
- [ ] Create `MANIFEST.in` to include `acm2/app/static/**/*`.
- [ ] Update FastAPI app to mount static files and serve `index.html` for SPA routing.
    - Serve `/assets` from static folder.
    - Catch-all route for other paths -> return `index.html`.
 - [ ] Add `scripts/build_ui.py` that builds the UI and stages artifacts under `app/static`.

## 3. CLI Entry Point
- [ ] Ensure `acm2/cli.py` is importable and runnable as an entry point.
- [ ] Verify `acm2 serve` launches Uvicorn.
- [ ] Verify `acm2` commands work when installed.

## 4. Build & Install Process
- [ ] Create a build script (e.g., `scripts/build.ps1` or `Makefile`) that:
 - [ ] Create a build script (e.g., `scripts/build.ps1` or `Makefile`) that:
     1. Installs npm deps.
     2. Builds frontend.
     3. Copies/moves build artifacts to Python package source (`app/static`).
     4. Builds Python wheel.
 - [ ] Expose `make build-ui` as a shortcut to run the standardized UI staging step.
- [ ] Test installation in a fresh virtual environment.

## 5. Configuration Management
- [ ] Ensure `config.yaml` is looked up in user home (`~/.acm2/`) or env vars.
- [ ] Ensure database is created in a persistent user location (not inside site-packages).

## 6. Verification
- [ ] `pip install .`
- [ ] `acm2 serve`
- [ ] Open browser -> Dashboard loads.
