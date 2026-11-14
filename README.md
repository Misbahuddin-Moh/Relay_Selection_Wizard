# Relay Selection Wizard

**Foundation alpha:** public provider operations are disabled. Use manual drawing entry or a concept study and deterministic station checks. CT quantities carry unreviewed origin metadata; digital budgets remain partial and cannot establish complete I/O fit or procurement readiness. See [status](docs/STATUS.md), [decisions](docs/DECISIONS.md), and [quality trace](docs/QUALITY_TRACE.md).

A preliminary protection study workspace for a synthetic single-transformer, single-collector-bus station. The baseline has three collector breaker positions serving five outgoing branches. Create a scenario to change measurement availability or feeder layout, then compare its findings with the baseline.

## Run locally

Use Python 3.12+ and Node.js 22.12+. On macOS or Linux, check with `python3 --version` and `node --version`.

Clone the repository and enter its directory. If you already cloned it, `cd` into your existing checkout instead.

```sh
git clone https://github.com/Misbahuddin-Moh/Relay_Selection_Wizard.git
cd Relay_Selection_Wizard
```

From the repository root on macOS or Linux, run:

```sh
python3 -m venv .venv &&
  .venv/bin/python -m pip install -r requirements-dev.txt &&
  npm --prefix frontend ci &&
  npm --prefix frontend run build &&
  .venv/bin/python -m uvicorn backend.main:app --port 8000
```

On Windows, create the environment with `py -3 -m venv .venv` and run the subsequent commands from the repository root using `.venv\Scripts\python.exe` as the environment’s Python executable.

Once Uvicorn starts, leave that terminal open and visit http://localhost:8000.

For frontend development, run `npm --prefix frontend run dev` with the API still running on port 8000 and open the address Vite prints.

```sh
.venv/bin/python -m unittest discover -s tests -v
npm --prefix frontend run build
```

## Start a concept study

Choose **New protection study** from the workspace. Enter a study name and the voltage levels, then add one collector bay per breaker position. Expand each bay to edit its breaker tag, assign the branches it serves, and review CT counts in the next step.

Select **Review topology** to check the one-line and review the CT inventory, then **Confirm and analyze** to make it the active baseline. Create a **New scenario** to test a change against that baseline. After the first successful analysis, the active study, pending scenario inputs and relay choices recover from this browser. Download a project JSON file for transfer. Earlier comparison history and source files are excluded; see [portable projects](docs/PROJECTS.md).

## Start from a one-line drawing

Choose **New protection study → Upload a drawing**. Select a PDF, PNG, or JPEG up to 20 MiB. The app wraps images above the provider’s inline threshold in a PDF without reducing their pixel resolution. The source preview uses your original file. A direct PDF export is preferable when available. **Enter manually** keeps the original available while you enter the topology without sending the file to an extraction service.

Public extraction is disabled in the foundation alpha. The inherited provider setup below is retained for future secured integration. For Claude extraction, set `ANTHROPIC_API_KEY` in the terminal that runs Uvicorn. On macOS with zsh, stop the running server first, then enter:

```zsh
read -rs 'ANTHROPIC_API_KEY?Claude API key: '
export ANTHROPIC_API_KEY
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

The server uses Claude Sonnet 4.6 when `ANTHROPIC_API_KEY` is set. With only `OPENAI_API_KEY`, it uses OpenAI with `gpt-4.1`. You can set `RELAY_DRAWING_MODEL` to a model supported by the selected provider. Clicking **Extract topology** sends the drawing to the provider shown in the upload screen. Use synthetic or approved drawings, and keep the extraction endpoint local until authenticated access is in place.

Compare the proposed fields and extraction notes with the source, correct the draft, and choose **Review topology**. Only **Confirm and analyze** runs the engineering checks.

## Review the CT inventory

Both entry paths show editable CT counts after the topology review. Breaker counts default to two CTs per phase on each breaker side. The collector counts apply uniformly to each physical collector breaker. Transformer phase counts default to three per phase on each side, with two separate neutral CTs per side. Enter zero where none exist or clear a count to leave it unknown.

Default quantities remain **assumed**. Editing one quantity records **user** origin without claiming it is engineer-reviewed. Older quantities without metadata have unknown origin. The wizard derives the HV boundary from the selected HV CT location (POI side by default) and each collector boundary from the collector breaker PV circuit-side count. The transformer LV phase count supplies the incomer boundary for the separate-zone comparison. Zero means Absent, a positive count means Present, and a blank count means Unknown.

Positive CT counts establish modeled presence only; they do not establish confirmation, CT suitability or independence. The inventory records quantities for the study and its what-if scenarios. Review boundary location, CT suitability, and assignment to primary and backup protection separately. Check winding grounding and the intended ground differential or restricted earth fault application before assigning neutral CTs. Phase-bank requirements are calculated from modeled measurement boundaries.

## Review protection areas

In the CT inventory, choose the station differential HV boundary and optionally include the POI line in the study. The zone review counts one local feeder area per collector breaker and shows the circuits served by that breaker. It also shows how selecting a different HV CT moves the station differential span. The optional POI line area is a preliminary 87L example with remote information left open. Coverage and trip targets remain subject to engineering review.

## Provider functionality (disabled in this alpha)

All public AI/extraction POST routes return HTTP 403, regardless of configured credentials. The following describes the inherited provider implementation for later secured integration; setting a key does not enable it. Do not put production keys on staging.

### Inherited option generation

From an analyzed study, select **Generate protection options**. This uses the server's `ANTHROPIC_API_KEY` and defaults to `claude-sonnet-4-6`. Set `RELAY_OPTIONS_MODEL` to select another Claude model that supports the structured response. The request sends grouped station facts and curated evidence. Drawing bytes, study titles, and equipment tags stay local.

Generation is on demand, with up to three proposals. The prompt aims for 300–600 output tokens and encourages shorter responses when enough. The API has a separate 4,096-token safety ceiling. Successful results are cached in memory for up to 32 distinct request summaries per server process. The UI shows token usage reported for the original generation. The wizard checks each proposed boundary locally and displays preliminary trip targets. Verify CT assignments, relay capability, owner requirements, and clearing paths before advancing a design.

## Study scope

The example baseline is synthetic. The active station and pending scenario inputs recover after refresh; earlier comparison history is excluded. A missing CT blocks the corresponding modeled differential boundary, while an unknown CT prompts confirmation. The input budget assumes one phase CT bank per collector breaker position and counts the auxiliary boundary separately when selected. Trip targets are preliminary and assume potential collector backfeed and no LV main breaker. Confirm actual CT locations and performance, auxiliary and remote trip paths, fault contributions, breaker failure, and owner requirements independently.

This milestone covers concept entry, topology review, and preliminary candidate comparison. Portable study JSON, local recovery and stable study/breaker/role identities are implemented. Shared project storage, manufacturer-validated ordering and report export remain later milestones.

## Review relay signals and project excerpts

After choosing a scheme, **Review relay signals** shows the modeled CT locations and protection functions for each role. Neutral and VT inputs may be left blank. The optional **Project documents and requirements** panel sends text from an approved UTF-8 excerpt or text-readable PDF to Claude when you click **Extract ordering requirements**. Set `ANTHROPIC_API_KEY` on the server. `RELAY_REQUIREMENTS_MODEL` optionally overrides the Claude model.

The first pass accepts excerpts of up to 30 PDF pages, 5 MiB and 90,000 extracted characters per request. It reports pages with little or no readable text. Scans can be transcribed and pasted. Findings retain the source excerpt and page. Claude matches excerpts to the selected scheme’s relay roles. Explicit required neutral CT and VT minimums apply automatically to valid matches. Unmatched excerpts stay visible without affecting screening. Other findings stay visible as ordering decisions for review. Both transformer relay families show partial configurations pending exact vendor and project checks.

## Package for hosting

The same FastAPI process serves the API and the built frontend. Deploy the container on a Python-capable host with HTTPS and private access in front of the app. Configure provider credentials as server environment variables and set the host's port through `PORT` if required. The workflow and URLs are identical to the local build. Access control for a live pilot belongs at the hosting layer. Keep provider credentials out of the image and enable uploads only for authorized users.

```sh
docker build -t relay-wizard .
docker run --rm -p 127.0.0.1:8000:8000 relay-wizard
```

## Quality and staging release

Install development dependencies with `pip install -r requirements-dev.txt` and `npm --prefix frontend ci`. Install the browser with `cd frontend && npx playwright install chromium` or set `CHROMIUM_EXECUTABLE_PATH` to an existing Chromium binary.

Run `bash scripts/verify.sh` for backend HTTP/unit tests, digital-budget tests, production build and browser smoke checks. Normal verification unsets provider keys and makes no paid requests.

On `staging/quality-foundation`, stage only reviewed changes and run `bash scripts/release-staging.sh "Describe the change"`. It verifies before committing and pushing. CI advances `staging/release` only after all checks (including browser checks) pass; Render tracks that release branch. The staging container also runs unit/build gates before deployment. Inspect the resulting Render deploy, `/api/health` revision, static assets and protected endpoints; a pushed commit or accepted deploy is not proof of a live release. Production promotion remains separate.

## Save and recovery

Use **Download project** for a portable JSON file. **Open project file** validates first and opens a separate copy only after you choose **Open imported copy**. After the first analysis, browser recovery saves the active station, pending edits and relay choices. The save panel reports failures and pauses when another tab changes the same study. Pending scenario edits support undo/redo. Source drawings/excerpts and earlier comparison history are excluded. [Full contract and limitations](docs/PROJECTS.md).

## Backend I/O assessment

The signal budget, nominal card comparison and ordering-request digital totals now use one versioned backend result. Open **Full endpoint signal ledger** to inspect relay and field contacts, coil drives, inclusion conditions and missing drawing references. Fast and form-C requirements can be entered per output; absent manufacturer capabilities stay unverified. Budgets remain partial and cannot establish purchasing readiness. [Engineering I/O contract and evidence limits](docs/ENGINEERING_IO.md).
