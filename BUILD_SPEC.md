# Data Quality IQ — Build Spec for Scaffolding

Full-stack MVP. Backend = Python FastAPI (analytics engine). Frontend = Next.js 14 (App Router) + TypeScript + Tailwind + shadcn/ui. Deploy: backend on Render (free), frontend on Vercel (free). LLM = Groq free tier.

The product: user uploads a CSV, backend runs deterministic data-quality engines, computes a 0-100 health score, sends ONLY computed diagnostics (never raw data) to Groq for an executive summary + recommendations, returns JSON. Frontend renders a polished startup-quality report.

## ALREADY WRITTEN (do not overwrite — build against these contracts)
- `backend/dqi/report.py` — `Severity` enum, `Finding` dataclass, `Report` dataclass (with `.to_dict()`).
- `backend/dqi/config.py` — all thresholds/weights/limits + `grade_for(score)`.
- `backend/dqi/engines/base.py` — `Engine` ABC with `run()` and never-raise `safe_run()`.

## BACKEND FILES TO CREATE

### `backend/dqi/schema.py`
`infer_schema(df) -> dict`. For each column return: dtype_inferred (one of numeric/categorical/datetime/boolean/text/id), n_unique, cardinality_ratio, null_rate, sample_values (3, stringified), is_id_like, is_high_cardinality, is_constant. Detect numeric-stored-as-string (try pd.to_numeric). Detect datetime by attempting parse on a sample. Use thresholds from config. Return {"columns": {col: profile...}, "n_numeric":..., "n_categorical":..., "n_datetime":..., "n_id_like":...}.

### Engines (each subclass `Engine`, set `name`, implement `run`):
- `engines/missingness.py` (name="missingness"): per-column null rate -> Finding with severity by config bands. Detect co-missing column groups via correlation of isna() masks > COMISSING_CORR. fix_snippet examples: drop col, impute. metrics include null_rate.
- `engines/duplicates.py` (name="duplicates"): exact duplicate rows count+rate; if id-like column exists, duplicate IDs with differing target -> CRITICAL (label noise). metrics: dup_count, dup_rate.
- `engines/imbalance.py` (name="imbalance"): only if target provided AND target is categorical/boolean/low-cardinality. Class proportions, imbalance ratio (max/min). Severity by config. Recommend stratified split, class_weight, PR-AUC. metrics: class_proportions dict, ratio.
- `engines/outliers.py` (name="outliers"): numeric cols only. IQR rule + robust z (median/MAD via scipy or numpy). Report % outliers per column. Severity by rate. Recommend robust scaling/winsorize/log. metrics: outlier_rate, n_outliers.
- `engines/leakage.py` (name="leakage") — THE HERO. Heuristics: (1) if target given, mutual_info_classif/regression on a sample (cap LEAKAGE_SAMPLE_ROWS) — feature with normalized MI or |corr| >= LEAKAGE_MI_CRITICAL -> CRITICAL perfect predictor; (2) suspicious column name regex (config.LEAKAGE_NAME_PATTERN) AND corr-with-target > LEAKAGE_CORR_SUSPICIOUS -> HIGH; (3) column equal to / monotonic transform of target -> CRITICAL; (4) id-like column used as feature -> HIGH (memorization); (5) duplicates + target present -> warn random splits leak. Encode categoricals (factorize) before MI. Handle both classification (target categorical) and regression (target numeric). metrics: mi, corr. Each Finding must have strong `impact` text + fix_snippet (drop the column).
- `engines/feature_quality.py` (name="feature_quality"): constant/quasi-constant (NEAR_ZERO_VARIANCE_RATIO), high-cardinality categoricals, near-duplicate numeric columns (|corr|>NEAR_DUPLICATE_CORR -> recommend dropping one), mixed-type columns, numeric-as-string. fix_snippets accordingly.
- `engines/correlation.py` (name="correlation"): numeric Pearson matrix; flag strongly correlated pairs (>STRONG_CORR) as INFO/MEDIUM redundancy. Provide the full matrix in metrics for the heatmap (as {"matrix": [[...]], "labels": [...]}). Keep matrix to numeric columns, cap at ~30 cols for size.

### `backend/dqi/scoring.py`
`score_report(findings) -> (health_score: float, grade: str, severity_counts: dict)`. Start 100, subtract SEVERITY_WEIGHTS per finding, cap per-engine total at CATEGORY_CAP, clamp [0,100], round 1dp. Also set each finding.score_penalty to the applied penalty. grade via config.grade_for.

### `backend/dqi/utils/sampling.py`
`maybe_sample(df) -> (df_sampled, sampled: bool)` honoring MAX_ROWS_ANALYZED with SAMPLE_RANDOM_STATE.

### `backend/dqi/utils/hashing.py`
`fingerprint(schema, finding_codes) -> str` sha256[:16] of sorted column dtypes + sorted finding codes + shape.

### `backend/dqi/ai/groq_client.py`
Thin wrapper over Groq Python SDK (`from groq import Groq`). Reads GROQ_API_KEY from env. `chat(system, user) -> str` with: retry (2x), timeout, and on 429/missing-key/any error return None (caller degrades gracefully). On-disk cache in `.cache/` keyed by sha256 of (system+user) so identical requests cost zero. Expose `is_configured() -> bool`.

### `backend/dqi/ai/prompts.py`
SYSTEM prompt (senior ML data-quality expert; receives deterministic diagnostics, never raw data; never invent numbers; for each issue state downstream ML consequence + concrete fix). `build_user_prompt(context_json) -> str` asking for: (1) 3-4 sentence exec summary pasteable into Slack, (2) prioritized action list max 5, each with what/why-for-model/one-line pandas snippet. Ask for STRICT JSON output: {"exec_summary": str, "recommendations": [str,...]}.

### `backend/dqi/ai/summarizer.py`
`build_context(report) -> dict`: compact JSON — dataset {name,rows,cols}, health_score, grade, schema_summary counts, top TOP_FINDINGS_FOR_LLM findings (severity-sorted) as {code,severity,column,title,impact,metrics-trimmed}. NO raw data. `summarize(report) -> (exec_summary, recommendations, ai_available)`: build context, call groq_client.chat, parse JSON; on failure build a deterministic fallback exec_summary + recommendations from findings (so product works with LLM off) and set ai_available False.

### `backend/dqi/pipeline.py`
`analyze(df, dataset_name, target=None) -> Report`: maybe_sample -> infer_schema -> run all engines via safe_run -> score -> fingerprint -> Report -> summarize (fill exec_summary/recommendations/ai_available) -> return. Also `analyze_csv_bytes(raw: bytes, name, target=None)` that validates size, parses CSV (encoding fallback utf-8 then latin-1), enforces MAX_COLS, raises ValueError with clear message on bad input.

### `backend/dqi/__init__.py`
Export `analyze`, `analyze_csv_bytes`, `Report`, `Finding`, `Severity`.

### `backend/app.py` (FastAPI)
- CORS enabled (allow the Vercel domain + localhost).
- `GET /health` -> {"status":"ok"} (for Render keep-alive).
- `GET /demos` -> list of demo dataset ids + descriptions.
- `POST /analyze` (multipart file upload, optional form field `target`): validate, call analyze_csv_bytes, return report.to_dict(). 400 on bad input.
- `POST /analyze/demo` (json {demo_id, target?}): load from data/demos, analyze, return.
- Rate limiting: simple in-memory token bucket keyed by client IP (e.g. slowapi or a tiny custom dict): 20 analyses/IP/hour. Return 429 with friendly message.
- File size / row / col caps enforced (config).
- Wrap handlers in try/except -> clean JSON errors. Use python logging (never log raw data, only shapes + codes).

### `backend/requirements.txt`
fastapi, uvicorn[standard], python-multipart, pandas, numpy, scipy, scikit-learn, groq, slowapi (or implement custom), python-dotenv.

### `backend/data/demos/`
Create THREE CSVs via a small generator script `backend/make_demos.py` (run it):
- `clean.csv` ~2000 rows, well-behaved (should score ~A/B).
- `messy.csv` ~3000 rows: missingness, duplicates, constant col, high-card id, outliers, class imbalance (should score ~C/D).
- `leaky.csv` ~2000 rows: a binary target plus an obvious leakage column (near-perfect predictor) and a suspiciously named `outcome_score` column (should score F with CRITICAL leakage).
Also create `backend/.env.example` with GROQ_API_KEY=, and `backend/Procfile` (`web: uvicorn app:app --host 0.0.0.0 --port $PORT`) + `backend/render.yaml` for Render.

### `backend/tests/`
pytest tests: test_leakage (leaky.csv yields a CRITICAL leakage finding), test_missingness, test_scoring (clean > messy > leaky). fixtures use the demo generator.

## FRONTEND (Next.js 14 App Router + TS + Tailwind + shadcn/ui) in `frontend/`
Initialize a Next.js app. Use shadcn/ui components (Button, Card, Badge, Progress, Tabs, Alert, Skeleton, Separator). Charts: use `recharts` (already React-friendly) for missingness bar, correlation heatmap (custom grid), imbalance donut/pie, outliers bar. Use lucide-react icons.

Design: modern, clean, startup-grade. Indigo accent (#4F46E5). Generous spacing, rounded-2xl cards, subtle shadows. Light theme (optionally dark toggle). Mobile-responsive.

Pages/components:
- `app/page.tsx`: single-page narrative.
  - Header: wordmark "DataQuality IQ" + GitHub link + "How it works".
  - Hero: headline "Know what's wrong with your dataset before you waste a week training on it." + subcopy.
  - Upload zone: drag-and-drop CSV (react-dropzone) + optional target column input + 3 demo buttons (Clean / Messy / Leaky).
  - On submit: POST to backend (env NEXT_PUBLIC_API_URL), show loading skeleton with rotating status messages (handle Render cold start gracefully — message "Waking up the analysis engine…").
  - Results: ScoreCard (gauge using a radial/recharts or custom SVG arc, big number /100 + grade badge color-coded), at-a-glance stats (rows, cols, severity counts).
  - ExecutiveSummary card (bordered, 📋).
  - Findings list: severity-sorted accordion cards; colored severity badge; "Why it matters" + detail + copy-able fix snippet (code block with copy button).
  - Charts in Tabs: Missingness | Correlation | Imbalance | Outliers.
  - Download report button (generate Markdown client-side from the JSON).
  - Empty + error states that look intentional.
- `lib/api.ts`: typed client (interfaces mirroring Report/Finding). functions analyze(file,target), analyzeDemo(id,target), getDemos.
- `lib/types.ts`: TS interfaces for Report/Finding/Severity.
- Severity color map matching backend.
- `.env.example` with NEXT_PUBLIC_API_URL=http://localhost:8000.
- `vercel.json` if needed. README in frontend with run/deploy steps.

## ROOT
- `README.md`: product pitch, screenshot placeholders, architecture diagram (text), local dev (backend: uvicorn; frontend: npm run dev), deployment (Render + Vercel + Groq secret), env vars.
- `.gitignore`: node_modules, .next, __pycache__, .env, .cache, *.pyc, venv.

## QUALITY BARS
- Backend must run headless end-to-end: `python -c "import dqi; print(dqi.analyze_csv_bytes(open('data/demos/leaky.csv','rb').read(),'leaky').health_score)"` works and leaky scores low.
- All engines never raise (safe_run).
- Never send raw data to LLM — only computed diagnostics.
- Product fully usable with Groq OFF (deterministic fallback).
- Frontend builds (`npm run build`) with no type errors.
- Run the backend tests; they must pass.
