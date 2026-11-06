# Relay Selection Wizard

A preliminary protection study workspace for a synthetic single-transformer, single-collector-bus station. The baseline has three collector breaker positions serving five outgoing branches. Create a scenario to change measurement availability or feeder layout, then compare its findings with the baseline.

## Run locally

Use Python 3.12+ and Node.js 22.12+.

```sh
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
npm --prefix frontend ci
npm --prefix frontend run build
.venv/bin/python -m uvicorn backend.main:app --port 8000
```

Open http://localhost:8000. On Windows, use `.venv\Scripts\python.exe` in place of `.venv/bin/python`.

For frontend development, run `npm --prefix frontend run dev` with the API still running on port 8000 and open the address Vite prints.

```sh
python -m unittest discover -s tests -v
npm --prefix frontend run build
```

## Study scope

The baseline is synthetic. Scenario edits stay in the current page and reset when it reloads. A missing CT blocks the corresponding modeled differential boundary, while an unknown CT prompts confirmation. The input budget assumes one phase CT bank per collector breaker position and counts the auxiliary boundary separately when selected. Trip targets are preliminary and assume potential collector backfeed and no LV main breaker. Confirm actual CT locations and performance, auxiliary and remote trip paths, fault contributions, breaker failure, and owner requirements independently.

This milestone covers topology editing and preliminary candidate comparison. Drawing extraction, persistent study storage, manufacturer-specific relay selection, and report export are planned for later milestones.
