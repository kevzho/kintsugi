# Kintsugi

**Know what's wrong with your dataset before you waste a week training on it.**

Upload a CSV and get a 0–100 data-quality health score, target-leakage detection, class-imbalance and outlier diagnostics, and a paste-ready executive summary — in seconds.

Deterministic analytics engines do the heavy lifting; an LLM (Groq) writes the human-readable summary from **computed diagnostics only — raw data is never sent to the model and never stored**.

The product is fully usable with the LLM **disabled**: when no `GROQ_API_KEY` is set, the summary and recommendations are produced by a deterministic fallback.

---

## Why Kintsugi

Kintsugi is the Japanese art of repairing broken objects with gold, treating breakage as something to understand and repair rather than hide. That maps naturally to data quality: broken datasets should be diagnosed clearly before model training begins. [web:35][web:44][web:47]

Target **leakage** is the single most expensive data-quality bug in applied ML: a
feature that secretly encodes the label makes offline metrics look perfect and the
model collapse in production. DataQuality IQ checks leakage with a
layered heuristic stack (mutual information, correlation, name patterns, target
copies, id memorization, duplicate-split leaks) and flags it as **CRITICAL** before
you train.

## Architecture

```text
                    ┌─────────────────────────────────────────┐
  CSV upload  ──▶   │  FastAPI (app.py)                        │
  / demo            │   -  input caps (10MB / 100k rows / 200c) │
                    │   -  per-IP rate limit (20/hr)            │
                    │   -  clean JSON errors                    │
                    └───────────────┬─────────────────────────┘
                                    │  dqi.analyze_csv_bytes()
                    ┌───────────────▼─────────────────────────┐
                    │  dqi  (pure library, no web imports)     │
                    │   sample → infer_schema → engines        │
                    │   ├ missingness   ├ outliers             │
                    │   ├ duplicates    ├ leakage              │
                    │   ├ imbalance     ├ feature_quality      │
                    │   └ correlation                          │
                    │   → score → fingerprint → Report         │
                    │   → summarizer (Groq or deterministic)   │
                    └───────────────┬─────────────────────────┘
                                    │  Report.to_dict()  (JSON)
                    ┌───────────────▼─────────────────────────┐
                    │  Next.js 14 frontend (Vercel)            │
                    │   score gauge · findings · charts · MD   │
                    └──────────────────────────────────────────┘
```

The `dqi` package imports **no** web framework, so it can be served by FastAPI, reused as a CLI, or dropped into a CI job / GitHub Action.

---

## Repository layout

```text
backend/
  dqi/                 pure analytics library
    report.py          Severity / Finding / Report (spine)
    config.py          all thresholds & weights (spine)
    schema.py          per-column type inference & profiling
    engines/           diagnostics engines
    scoring.py         weighted, per-engine-capped health score
    ai/                groq_client (cached, degrades) + summarizer
    utils/             sampling + fingerprint
    pipeline.py        analyze() / analyze_csv_bytes()
  app.py               FastAPI server
  make_demos.py        generates clean/messy/leaky CSVs
  tests/               pytest (leakage, missingness, scoring ordering)
frontend/              Next.js 14 + TypeScript + Tailwind + Recharts
```

---

## How it works

1. A CSV is uploaded through the web UI or sent to the backend.
2. The backend validates file size and dataset limits.
3. The `dqi` library samples and profiles the dataset.
4. Diagnostic engines evaluate missingness, duplicates, outliers, leakage, imbalance, feature quality, and correlations.
5. A weighted scoring system computes the health score and grade.
6. A summary is generated:
   - With `GROQ_API_KEY`: an LLM writes a human-readable summary from computed diagnostics only.
   - Without `GROQ_API_KEY`: a deterministic fallback generates the summary and recommendations.
7. The frontend renders findings, charts, and a paste-ready summary.

---

## Local development

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python make_demos.py
cp .env.example .env
uvicorn app:app --reload
pytest
```

Backend runs at:

```text
http://localhost:8000
```

### Headless sanity check

```bash
python -c "import dqi; r=dqi.analyze_csv_bytes(open('data/demos/leaky.csv','rb').read(),'leaky'); print(r.health_score, r.grade)"
```

Expected example output:

```text
23.0 F
```

A severely leaky demo dataset should also include a **CRITICAL** leakage finding.

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Frontend runs at:

```text
http://localhost:3000
```

---

## Deployment

### Backend on Render

- `render.yaml` is included.
- Create a new **Web Service** from the repository.
- Set the root directory to `backend/`.

Build command:

```bash
pip install -r requirements.txt && python make_demos.py
```

Start command:

```bash
uvicorn app:app --host 0.0.0.0 --port $PORT
```

Notes:
- `Procfile` may also contain the same start command.
- `GROQ_API_KEY` is optional.
- If the key is omitted, the app runs fully in deterministic mode.
- On the free tier, cold starts are expected; the frontend can show a brief “Waking up the analysis engine…” message.
- `/health` is intended to be a cheap health-check / keep-alive endpoint.

### Frontend on Vercel

- Import the repository into Vercel.
- Set the project root to `frontend/`.
- Add the environment variable:

```text
NEXT_PUBLIC_API_URL=<your-backend-url>
```

- Deploy.

### Groq configuration

Get an API key from:

```text
https://console.groq.com/keys
```

Set `GROQ_API_KEY` on the backend to enable LLM-generated executive summaries.

Model settings and limits live in:

```text
backend/dqi/config.py
```

Responses are cached on disk in:

```text
.cache/
```

Cache entries are keyed by a hash of the prompt so repeated analyses can reuse existing summaries.

---

## Environment variables

| Variable              | Where     | Default                    | Purpose                                |
|-----------------------|-----------|----------------------------|----------------------------------------|
| `GROQ_API_KEY`        | backend   | unset                      | Enables LLM executive summaries        |
| `KINTSUGI_USAGE_LOG_PATH` | backend | `.usage/kintsugi_usage_events.jsonl` | Optional JSONL file for anonymous completed-analysis events. Set to `off` to disable file writes. Events are always emitted to backend logs as `kintsugi_usage_event`. |
| `NEXT_PUBLIC_API_URL` | frontend  | `http://localhost:8000`    | Backend base URL used by the frontend  |

---

## Limits and safeguards

The API is designed with practical guardrails for reliability and cost control.

Current defaults:
- Maximum upload size: `10MB`
- Maximum rows: `100,000`
- Maximum columns: `200`
- Per-IP rate limit: `20 requests / hour`

These values can be adjusted in backend configuration if deployment requirements change.

---

## Privacy

Kintsugi is designed to minimize data exposure.

- Raw dataset rows never leave the backend process.
- Raw rows are never sent to the LLM.
- Raw rows are never stored for summary generation.
- Only computed diagnostics such as counts, rates, correlations, and finding codes are sent to the LLM.
- The application remains fully usable with the LLM disabled.

## Anonymous Usage Tracking

Kintsugi is free to use and does not require accounts. To measure impact, each completed upload or demo analysis records a small anonymous event:

- Anonymous browser visitor ID and session ID
- Timestamp, source (`upload` or `demo`), file extension, row count, and column count
- Score, grade, severity counts, finding count, and whether AI summaries were available
- Hashed IP/user-agent metadata for coarse duplicate detection

Raw uploaded rows, cell values, column names, and uploaded filenames are never written to usage events. The backend emits events to logs as `kintsugi_usage_event` and, by default, appends JSONL locally at `.usage/kintsugi_usage_events.jsonl`. On Render or another ephemeral host, use log drains for durable production measurement, or set `KINTSUGI_USAGE_LOG_PATH` to a persistent mounted path if one is available.

Impact metrics:

- Users = count distinct `anonymousUserId` values.
- Submissions = count `analysis_completed` events.
- Demo usage = count events where `source` is `demo`.
- Upload usage = count events where `source` is `upload`.

---

## Deterministic mode

If no `GROQ_API_KEY` is configured:
- analysis still runs normally,
- scoring still works,
- findings still render,
- summaries and recommendations are produced by a deterministic fallback.

This makes the product usable in restricted, offline-ish, or privacy-sensitive environments where external model calls are not desired.

---

## Example use cases

- Validate a dataset before starting model training
- Catch target leakage before offline metrics become misleading
- Triage messy CSVs from business, healthcare, or finance workflows
- Add dataset quality gates to CI or internal ML tooling
- Generate quick executive summaries for non-technical stakeholders

---

## Future directions

Potential extensions include:
- CLI support for local and CI usage
- GitHub Action integration
- Dataset drift checks across train/validation/test splits
- More advanced schema and semantic anomaly detection
- Team-facing reports and export formats
- Support for additional file formats beyond CSV

---

## Contributing

Contributions, bug reports, and feature suggestions are welcome.

Typical areas for contribution:
- new diagnostics engines,
- improved scoring heuristics,
- better frontend visualization,
- expanded test coverage,
- CLI / automation support,
- documentation improvements.

If contributing code, aim to keep the `dqi` package framework-agnostic and reusable outside the web app.

---

## License

Kintsugi is released under the MIT License. See the `LICENSE` file for details.
