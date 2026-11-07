# Relay Selection Wizard

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
  .venv/bin/python -m pip install -r requirements.txt &&
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

Select **Review topology** to check the one-line and review the CT inventory, then **Confirm and analyze** to make it the active baseline. Create a **New scenario** to test a change against that baseline. Concept studies and scenarios reset when you reload the page.

## Start from a one-line drawing

Choose **New protection study → Upload a drawing**. Select a PDF, PNG, or JPEG up to 20 MiB. The app wraps images above the provider’s inline threshold in a PDF without reducing their pixel resolution. The source preview uses your original file. A direct PDF export is preferable when available. **Enter manually** keeps the original available while you enter the topology without sending the file to an extraction service.

For Claude extraction, set `ANTHROPIC_API_KEY` in the terminal that runs Uvicorn. On macOS with zsh, stop the running server first, then enter:

```zsh
read -rs 'ANTHROPIC_API_KEY?Claude API key: '
export ANTHROPIC_API_KEY
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

The server uses Claude Sonnet 4.6 when `ANTHROPIC_API_KEY` is set. With only `OPENAI_API_KEY`, it uses OpenAI with `gpt-4.1`. You can set `RELAY_DRAWING_MODEL` to a model supported by the selected provider. Clicking **Extract topology** sends the drawing to the provider shown in the upload screen. Use synthetic or approved drawings, and keep the extraction endpoint local until authenticated access is in place.

Compare the proposed fields and extraction notes with the source, correct the draft, and choose **Review topology**. Only **Confirm and analyze** runs the engineering checks.

## Review the CT inventory

Both entry paths show editable CT counts after the topology review. Breaker counts default to two CTs per phase on each breaker side. The collector counts apply uniformly to each physical collector breaker. Transformer phase counts default to three per phase on each side, with two separate neutral CTs per side. Enter zero where none exist or clear a count to leave it unknown.

The wizard derives the HV boundary from the selected HV CT location (POI side by default) and each collector boundary from the collector breaker PV circuit-side count. The transformer LV phase count supplies the incomer boundary for the separate-zone comparison. Zero means Absent, a positive count means Present, and a blank count means Unknown.

The inventory records quantities for the study and its what-if scenarios. Review boundary location, CT suitability, and assignment to primary and backup protection separately. Check winding grounding and the intended ground differential or restricted earth fault application before assigning neutral CTs. Phase-bank requirements are calculated from modeled measurement boundaries.

## Review protection areas

In the CT inventory, choose the station differential HV boundary and optionally include the POI line in the study. The zone review counts one local feeder area per collector breaker and shows the circuits served by that breaker. It also shows how selecting a different HV CT moves the station differential span. The optional POI line area is a preliminary 87L example with remote information left open. Coverage and trip targets remain subject to engineering review.

## Generate AI protection options

From an analyzed study, select **Generate protection options**. This uses the server's `ANTHROPIC_API_KEY` and defaults to `claude-sonnet-4-6`. Set `RELAY_OPTIONS_MODEL` to select another Claude model that supports the structured response. The request sends grouped station facts and curated evidence. Drawing bytes, study titles, and equipment tags stay local.

Generation is on demand, with up to three proposals and a 1,400 output-token limit. Successful results are cached in memory for up to 32 distinct request summaries per server process. The UI shows token usage reported for the original generation. The wizard checks each proposed boundary locally and displays preliminary trip targets. Verify CT assignments, relay capability, owner requirements, and clearing paths before advancing a design.

## Study scope

The example baseline is synthetic. Scenario edits stay in the current page and reset when it reloads. A missing CT blocks the corresponding modeled differential boundary, while an unknown CT prompts confirmation. The input budget assumes one phase CT bank per collector breaker position and counts the auxiliary boundary separately when selected. Trip targets are preliminary and assume potential collector backfeed and no LV main breaker. Confirm actual CT locations and performance, auxiliary and remote trip paths, fault contributions, breaker failure, and owner requirements independently.

This milestone covers concept entry, topology review, and preliminary candidate comparison. Persistent study storage, manufacturer-specific relay selection, and report export are planned for later milestones.
