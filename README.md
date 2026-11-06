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

Choose **New protection study** from the workspace. Enter a study name and the voltage levels, then add one collector bay per breaker position. Expand each bay to edit its breaker tag, assign the branches it serves, and record CT availability. Leave unconfirmed measurements as **Unknown**.

Select **Review topology** to check the one-line, then **Confirm and analyze** to make it the active baseline. Create a **New scenario** to test a change against that baseline. Concept studies and scenarios reset when you reload the page.

## Start from a one-line drawing

Choose **New protection study → Upload a drawing**. Select a PDF, PNG, or JPEG up to 8 MiB. **Enter manually** keeps the original available while you enter the topology without sending the file to an extraction service.

For live extraction, set `OPENAI_API_KEY` in the terminal that runs Uvicorn. On macOS with zsh, stop the running server first, then enter:

```zsh
read -rs 'OPENAI_API_KEY?OpenAI API key: '
export OPENAI_API_KEY
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

The server defaults to `gpt-4.1`. You can set `RELAY_DRAWING_MODEL` to an approved model with PDF, image, and structured output support. Clicking **Extract topology** sends the drawing to OpenAI. Use synthetic or approved drawings, and keep the extraction endpoint local until authenticated access is in place.

Compare the proposed fields and extraction notes with the source, correct the draft, and choose **Review topology**. Only **Confirm and analyze** runs the engineering checks.

## Study scope

The example baseline is synthetic. Scenario edits stay in the current page and reset when it reloads. A missing CT blocks the corresponding modeled differential boundary, while an unknown CT prompts confirmation. The input budget assumes one phase CT bank per collector breaker position and counts the auxiliary boundary separately when selected. Trip targets are preliminary and assume potential collector backfeed and no LV main breaker. Confirm actual CT locations and performance, auxiliary and remote trip paths, fault contributions, breaker failure, and owner requirements independently.

This milestone covers concept entry, topology review, and preliminary candidate comparison. Persistent study storage, manufacturer-specific relay selection, and report export are planned for later milestones.
