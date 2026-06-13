# DataQuality IQ

**Know what's wrong with your dataset before you waste a week training on it.**

Upload a CSV and get a 0–100 data-quality health score, target-leakage detection,
class-imbalance and outlier diagnostics, and a paste-ready executive summary — in
seconds. Deterministic analytics engines do the heavy lifting; an LLM (Groq) writes
the human-readable summary from **computed diagnostics only — your raw data is never
sent to the model and never stored.**

The product is fully usable with the LLM **off**: when no `GROQ_API_KEY` is set, the
summary and recommendations are produced by a deterministic fallback.

---

## Why it exists

Target **leakage** is the single most expensive data-quality bug in applied ML: a
feature that secretly encodes the label makes offline metrics look perfect and the
model collapse in production. DataQuality IQ checks leakage with a
layered heuristic stack (mutual information, correlation, name patterns, target
copies, id memorization, duplicate-split leaks) and flags it as **CRITICAL** before
you train.

## Architecture

```
                    ┌─────────────────────────────────────────┐
  CSV upload  ──▶   │  FastAPI (app.py)                        │
  / demo            │   • input caps (10MB / 100k rows / 200c) │
                    │   • per-IP rate limit (20/hr)            │
                    │   • clean JSON errors                    │
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

The `dqi` package imports **no** web framework, so it can be served by FastAPI,
reused as a CLI, or dropped into a CI job / GitHub Action.

## Repository layout

```
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
frontend/              Next.js 14 + TS + Tailwind + Recharts
```

## Local development

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python make_demos.py                 # generate demo CSVs
cp .env.example .env                 # optional: add GROQ_API_KEY
uvicorn app:app --reload             # http://localhost:8000
pytest                               # run the test suite
```

Headless sanity check:

```bash
python -c "import dqi; r=dqi.analyze_csv_bytes(open('data/demos/leaky.csv','rb').read(),'leaky'); print(r.health_score, r.grade)"
# -> 23.0 F   (with a CRITICAL leakage finding)
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local           # NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev                          # http://localhost:3000
```

## Deployment

### Backend → Render (free)

- `render.yaml` is included. Create a new **Web Service** from the repo, root
  directory `backend/`.
- Build: `pip install -r requirements.txt && python make_demos.py`
- Start: `uvicorn app:app --host 0.0.0.0 --port $PORT` (also in the `Procfile`).
- Set the `GROQ_API_KEY` env var (optional — omit to run in deterministic mode).
- The free tier sleeps; the frontend shows a "Waking up the analysis engine…"
  message and `/health` is a cheap keep-alive endpoint.

### Frontend → Vercel (free)

- Import the repo, set the project root to `frontend/`.
- Add env var `NEXT_PUBLIC_API_URL` = your Render backend URL.
- Deploy.

### LLM → Groq (free tier)

Get a key at <https://console.groq.com/keys> and set `GROQ_API_KEY` on the backend.
Model and limits are configured in `backend/dqi/config.py`. Responses are cached on
disk (`.cache/`) keyed by a hash of the prompt, so repeated analyses cost nothing.

## Environment variables

| Variable              | Where     | Default                  | Purpose                          |
|-----------------------|-----------|--------------------------|----------------------------------|
| `GROQ_API_KEY`        | backend   | _(unset → deterministic)_| Enables the LLM executive summary |
| `NEXT_PUBLIC_API_URL` | frontend  | `http://localhost:8000`  | Backend base URL                  |

## Privacy

Raw rows never leave the backend process and are never written to disk. Only computed
diagnostics (counts, rates, correlations, finding codes) are sent to the LLM.
