# Kintsugi Writeup Script

## 1. Opening

Kintsugi is a data-quality and model-readiness diagnostic tool for people who need to know whether a dataset is safe to use before they spend time training models, building dashboards, or making decisions from it.

The core idea is simple: most machine-learning failures do not start inside the model. They start upstream, in the dataset. Missing values, target leakage, duplicate rows, class imbalance, near-unique identifiers, high-cardinality categories, outliers, and weak target support can make a model look accurate in development and fail in production.

Kintsugi catches those problems before training begins.

The name comes from the Japanese art of repairing broken objects with gold. The metaphor is intentional: the goal is not to hide brokenness in data, but to expose it clearly, understand it, and make repair possible.

## 2. Product Value

Kintsugi answers a practical question:

> Is this dataset healthy enough to train on, or should we fix it first?

Instead of giving users a vague warning like "your data may be messy," Kintsugi produces:

- a 0-100 overall health score,
- a separate data-integrity score,
- a separate model-readiness score,
- a letter grade,
- a verdict such as "Ready for baseline modeling" or "Do not train until leakage is resolved,"
- ranked findings with severity,
- fix snippets where possible,
- and a paste-ready executive summary.

This makes it useful for:

- ML engineers checking datasets before experimentation,
- data scientists evaluating client or internal CSVs,
- product teams validating user-submitted datasets,
- students learning why model evaluation can fail,
- and organizations that need a quick, explainable data-quality gate.

The value is speed and clarity. A user can upload a CSV and know in seconds whether the dataset is clean, risky, or fundamentally unsuitable for supervised learning.

## 3. Core Methodology

Kintsugi uses a deterministic-first methodology.

The system does not ask an LLM to inspect raw data and make guesses. Instead, it runs a pipeline of rule-based and statistical diagnostic engines. Those engines compute measurable evidence: null rates, duplicate rates, cardinality ratios, outlier counts, mutual information, correlations, class balance, sample size, rows per feature, target support, and other dataset-level indicators.

The LLM, when enabled, is only used after that deterministic analysis is complete. It receives computed diagnostics only, not raw rows, and turns those diagnostics into a readable executive summary. If Groq is unavailable or no API key is configured, Kintsugi falls back to deterministic summary text.

That creates an important trust boundary:

- deterministic engines compute the facts,
- scoring logic assigns penalties,
- the report object stores evidence,
- and the LLM only writes prose from those facts.

## 4. End-to-End Flow

The end-to-end flow looks like this:

1. A user uploads a CSV through the frontend or sends one directly to the backend.
2. The FastAPI server validates the request.
3. The backend enforces file and shape limits.
4. The CSV is parsed into a pandas DataFrame.
5. The dataset may be sampled if it is very large.
6. Kintsugi infers the schema.
7. Kintsugi classifies dataset type and column roles.
8. Diagnostic engines run independently.
9. Findings are scored into integrity and readiness penalties.
10. A report fingerprint is generated.
11. A summary is produced using either Groq or deterministic fallback.
12. The frontend renders the score, findings, recommendations, charts, and summary.

The backend pipeline is centered around:

```text
dqi.analyze_csv_bytes()
  -> parse CSV
  -> maybe_sample()
  -> infer_schema()
  -> classify_dataset()
  -> classify_columns()
  -> run diagnostic engines
  -> score_report()
  -> fingerprint()
  -> summarize()
  -> Report
```

## 5. Architecture

Kintsugi has three major layers.

### Frontend

The frontend is a Next.js application. It gives users a simple interface for uploading datasets, selecting or reviewing target columns, and reading results.

It renders:

- score gauges,
- findings,
- severity indicators,
- charts,
- recommendations,
- and an executive summary.

The frontend is intentionally thin. It does not assign scores. It sends data to the backend and displays the resulting report.

### Backend API

The backend is a FastAPI service. It handles:

- upload validation,
- input limits,
- rate limits,
- clean error responses,
- demo endpoints,
- and report serialization.

The backend is the boundary between the web app and the pure analytics library.

### `dqi` Analytics Library

The `dqi` package is the core engine. It has no web-framework dependency, which means it can be reused outside the web app in the future as:

- a CLI,
- a CI quality gate,
- a GitHub Action,
- or an internal Python package.

This separation is important. The product is a web app, but the actual data-quality intelligence lives in a reusable library.

## 6. Model Architecture

Kintsugi's "model architecture" is not a single black-box model. It is a deterministic diagnostic architecture made of multiple specialized engines plus a scoring layer.

The architecture has these stages:

```text
CSV
  -> schema inference
  -> dataset classification
  -> column role classification
  -> diagnostic engines
  -> finding objects
  -> integrity/readiness scoring
  -> report
  -> optional LLM summary
```

Each diagnostic engine produces `Finding` objects. A finding includes:

- engine name,
- finding code,
- severity,
- title,
- detail,
- impact,
- affected column,
- optional fix snippet,
- metrics,
- and category.

Those findings are then converted into numeric penalties by the scoring layer.

## 7. Diagnostic Engines

Kintsugi uses a suite of targeted engines rather than one general-purpose heuristic.

### Missingness Engine

This engine identifies columns with missing values and distinguishes ordinary missingness from structural missingness patterns.

Why it matters:

- missing values can shrink training data,
- introduce bias,
- break model pipelines,
- or indicate that different data collection regimes are mixed together.

### Duplicate Engine

This engine detects duplicated rows.

Why it matters:

- duplicates can inflate evaluation metrics,
- contaminate train/test splits,
- and cause the same example to appear in both training and validation.

### Outlier Engine

This engine flags extreme numeric values.

Outliers are treated carefully. Kintsugi does not always treat them as data-integrity failures, because in domains like network logs or financial records, heavy tails may be real. The scoring layer can classify outliers as modeling warnings rather than integrity failures.

Why it matters:

- outliers can distort means and coefficients,
- destabilize models,
- and create misleading dashboards.

### Leakage Engine

The leakage engine is one of Kintsugi's most important components.

Target leakage happens when a feature contains information that would not be available at prediction time. It can make validation metrics look excellent while making the model useless in production.

Kintsugi checks leakage with a layered heuristic stack:

1. high mutual information with the target,
2. high absolute correlation with the target,
3. suspicious target-like column names,
4. exact copies of the target,
5. monotonic transforms of the target,
6. id-like columns that can cause memorization,
7. duplicate patterns that can leak across random splits.

The leakage engine handles both classification and regression targets. Categorical values are encoded for mutual-information checks, and numeric/categorical targets are treated differently.

The key design principle is conservatism. A highly associated feature is not automatically called leakage unless there is semantic or timing evidence. When evidence is weaker, Kintsugi labels the issue as a target-proxy risk or modeling warning rather than a confirmed data-integrity failure.

### Imbalance Engine

The imbalance engine evaluates class distribution for categorical or classification-like targets.

Why it matters:

- a model can appear accurate by predicting the majority class,
- rare classes may have too little support,
- and train/test splits may fail to represent minority outcomes.

### Feature Quality Engine

This engine identifies columns that are likely to hurt modeling quality:

- near-constant fields,
- high-cardinality categories,
- near-duplicate features,
- messy numeric text,
- mixed types,
- and low-information features.

Why it matters:

- models can overfit identifiers,
- memorize rare categories,
- or fail because a column that looks numeric is stored as inconsistent text.

### Correlation Engine

The correlation engine looks for strong relationships between numeric columns.

Why it matters:

- highly correlated features may be redundant,
- certain correlations can reveal duplicated measurements,
- and strong relationships may signal data leakage or derived variables.

Kintsugi treats correlation as association, not causation.

### Model-Readiness Engine

This engine separates "clean data" from "trainable data."

A dataset can have few missing values and still be unsuitable for supervised machine learning. The model-readiness engine checks:

- sample size,
- rows per feature,
- high-cardinality generalization risk,
- weak target support,
- post-outcome feature risk,
- whether a target column was selected,
- and the likely purpose of the dataset.

It can classify a dataset as:

- Not suitable for supervised ML,
- EDA-only / visualization dataset,
- Toy ML / demo only,
- Trainable with caution,
- Strong ML candidate.

This distinction is central to Kintsugi's value. It avoids telling users "your data is clean, so go train a model" when the dataset is structurally too small, too sparse, or too likely to leak.

## 8. Dataset and Column Classification

Before scoring, Kintsugi classifies the dataset context.

The dataset classifier uses deterministic heuristics to identify common dataset shapes:

- fixture schedules,
- historical archives,
- network logs,
- panel data,
- time series,
- supervised tabular ML,
- business tabular data,
- ecommerce datasets,
- survey data,
- scientific measurements,
- or unknown.

The column classifier labels columns as:

- target,
- identifier,
- timestamp,
- binary flag,
- measurement,
- text,
- derived feature,
- or categorical.

These roles help the diagnostic engines interpret columns correctly. For example, a near-unique column may be fine as an identifier, but risky as a model feature. A post-outcome column may be harmless in a report but dangerous in supervised learning.

## 9. Scoring System

Kintsugi uses a two-score architecture:

1. **Integrity score**
2. **Model-readiness score**

The overall health score combines the two.

### Integrity Score

The integrity score answers:

> Is the dataset internally clean and trustworthy?

It is affected by findings such as:

- missing values,
- duplicate rows,
- corrupted or mixed-type columns,
- structural missingness,
- and confirmed data-integrity problems.

### Model-Readiness Score

The readiness score answers:

> Is the dataset suitable for supervised machine learning?

It is affected by:

- target leakage,
- sample size,
- rows per feature,
- imbalance,
- high-cardinality features,
- weak class support,
- near-unique identifiers,
- post-outcome features,
- and other modeling warnings.

### Why Two Scores?

The two-score design is important because data can be clean but not model-ready.

For example:

- A World Cup historical archive may be clean and useful for visualization, but too small for reliable supervised ML.
- A cybersecurity dataset may have legitimate heavy-tailed byte counts that are not integrity failures, but they still affect modeling assumptions.
- A dataset with a copied target column may look predictive, but it is not valid for training.

By separating integrity and readiness, Kintsugi gives users a more accurate diagnosis.

## 10. Penalty Caps and Severity

Findings have severity levels:

- critical,
- high,
- medium,
- low,
- info.

The scoring layer maps these severities to penalties. It also uses per-engine caps so one class of issue does not dominate the score unfairly.

For example:

- outliers have a small cap on integrity penalty,
- model-readiness issues can have larger readiness penalties,
- target leakage can cap readiness and overall score,
- messy numeric text can create a stronger readiness penalty,
- and small datasets can cap the final purpose classification.

This is designed to make scores stable and interpretable.

## 11. Confidence System

Kintsugi also assigns confidence levels to the score interpretation.

Confidence is based on:

- number of findings,
- severity of findings,
- sample size,
- whether the dataset was sampled,
- whether the task is model-readiness or integrity,
- and whether target-dependent checks were actually applicable.

If there is no target column, supervised ML readiness is marked as not applicable rather than pretending the dataset was fully evaluated for modeling.

This matters because a score without confidence can be misleading. Kintsugi tries to say not just "here is the grade," but "here is how much evidence supports the grade."

## 12. Report Object

The backend produces a structured `Report`.

The report includes:

- dataset name,
- row and column counts,
- sampled status,
- target column,
- possible target suggestions,
- integrity score and grade,
- readiness score and grade,
- overall score and grade,
- verdict,
- confidence notes,
- dataset type,
- dataset purpose,
- severity counts,
- schema summary,
- findings,
- modeling warnings,
- recommendations,
- executive summary,
- and AI availability.

The report is serialized to JSON for the frontend.

## 13. LLM Layer

Kintsugi uses Groq optionally.

The LLM does not score the dataset. It does not inspect raw rows. It does not invent findings.

Instead, the summarizer builds a compact context from the report:

- dataset shape,
- scores,
- grades,
- confidence,
- dataset type,
- target column,
- possible targets,
- schema summary,
- severity counts,
- top findings,
- finding codes,
- impacts,
- metrics,
- and deterministic fix snippets.

That context is sent to Groq with instructions to return an executive summary and recommendations. If the response is missing, invalid, or unparseable, Kintsugi falls back to deterministic summary text.

This makes the LLM a communication layer, not a decision layer.

## 14. Deterministic Fallback

Kintsugi is fully usable without Groq.

If `GROQ_API_KEY` is not set:

- diagnostics still run,
- scores still compute,
- findings still render,
- recommendations still exist,
- and the executive summary is generated by deterministic logic.

This is important for privacy-sensitive users, demos, cost control, and environments where external model calls are not allowed.

## 15. Privacy Model

Kintsugi is designed to minimize data exposure.

Raw dataset rows:

- are processed by the backend,
- are not sent to Groq,
- are not stored for summary generation,
- and are not required for the LLM layer.

The LLM receives only computed diagnostics. These are aggregate or derived values such as counts, rates, severity codes, scores, and finding summaries.

This design supports the product's trust story:

> Kintsugi can explain what's wrong with a dataset without handing raw data to a model provider.

## 16. Reliability and Safeguards

Kintsugi includes operational guardrails:

- maximum upload size,
- maximum rows,
- maximum columns,
- deterministic sampling,
- per-IP rate limiting,
- safe engine execution,
- graceful summarizer fallback,
- and clean JSON error responses.

Each diagnostic engine runs through a safe wrapper so one failed check cannot crash the entire analysis.

The backend is built to return a useful report whenever possible.

## 17. Example Narrative

Here is how I would explain Kintsugi in a demo:

> Before training a model, most teams ask, "Which algorithm should we use?" Kintsugi asks the question that should come first: "Is this dataset even safe to train on?"
>
> I upload a CSV. Kintsugi profiles the schema, identifies likely target columns, checks for missingness, duplicates, outliers, leakage, imbalance, and feature-quality issues, then produces separate scores for data integrity and model readiness.
>
> This separation is important. A dataset can be clean but still not trainable. It may be too small, have too few examples per feature, include near-unique identifiers, or leak the target through post-outcome columns.
>
> The most dangerous issue is target leakage. Kintsugi checks leakage with multiple signals: mutual information, correlation, target-copy detection, suspicious names, id memorization, and duplicate split risk. If it finds a feature that appears to encode the target, it can cap the model-readiness score and warn the user not to train until that issue is resolved.
>
> Finally, Kintsugi generates an executive summary. If Groq is enabled, the LLM writes the summary from computed diagnostics only. If Groq is disabled, a deterministic fallback writes the summary. Either way, the score and findings come from the diagnostic engine, not from the LLM.

## 18. Technical Differentiators

Kintsugi has several differentiators:

1. **Deterministic-first scoring**
   Scores are not generated by a black-box LLM.

2. **Two-score architecture**
   Integrity and model readiness are separated.

3. **Leakage-first design**
   Target leakage is treated as a critical ML failure mode.

4. **Dataset-purpose classification**
   Kintsugi can say whether a dataset is better suited for ML, EDA, visualization, simulation, or historical analysis.

5. **Graceful LLM degradation**
   Groq improves readability but is not required.

6. **Reusable core library**
   The `dqi` package has no web dependency and can later become a CLI or CI tool.

7. **Privacy-conscious summarization**
   Raw rows are never sent to the LLM.

8. **Actionable output**
   Findings include impact language and fix snippets.

## 19. Business and User Value

Kintsugi saves time before model development begins.

Without a tool like this, teams often discover data problems after:

- training baseline models,
- debugging suspiciously high validation scores,
- investigating production failures,
- or manually profiling dozens of columns.

Kintsugi compresses that discovery process into seconds.

For a data scientist, it is a preflight checklist.

For a team lead, it is a risk report.

For a non-technical stakeholder, it is a readable explanation of whether the dataset is trustworthy.

For a student or educator, it is a teaching tool for the hidden failure modes of machine learning.

## 20. Suggested Short Pitch

Kintsugi is a preflight diagnostic tool for machine-learning datasets. Upload a CSV, choose a target column if you have one, and Kintsugi checks whether the data is clean, trainable, and safe from common ML traps like target leakage, class imbalance, duplicate rows, outliers, weak target support, and high-cardinality memorization.

Unlike a generic AI assistant, Kintsugi does not ask a model to guess what is wrong. It runs deterministic diagnostic engines, computes evidence-backed findings, assigns separate integrity and model-readiness scores, and then optionally uses Groq only to write a readable executive summary from those computed diagnostics.

The result is a fast, explainable report that tells users whether they can train, should clean first, or should treat the dataset as better suited for exploration rather than supervised ML.

## 21. Suggested Long Pitch

Most ML projects do not fail because the first model was not sophisticated enough. They fail because the dataset had problems that were invisible until too late.

Kintsugi is designed to catch those problems early.

The workflow is intentionally simple. A user uploads a CSV. The backend parses and profiles it, then runs a set of diagnostic engines. Each engine focuses on a specific failure mode: missing values, duplicates, outliers, leakage, imbalance, feature quality, correlations, and overall model readiness.

The most important design choice is that Kintsugi separates data integrity from model readiness. Integrity asks whether the data is internally clean. Readiness asks whether the data is suitable for supervised learning. Those are not the same thing.

For example, a historical archive might be complete and internally consistent, but too small or too non-repetitive for reliable supervised learning. A dataset might have clean columns and no missing values, but include a post-outcome feature that leaks the answer. Kintsugi is built to detect and explain those differences.

The scoring system is deterministic. Findings have severity, metrics, and penalties. Engine-level caps keep scores stable. Target leakage and severe corruption can cap the final grade. Small sample sizes and weak target support lower model-readiness confidence. The output is not just a number; it is a report with evidence.

Kintsugi also includes an optional Groq summary layer. This is not where the analysis happens. The LLM receives a compact list of computed diagnostics and writes a readable summary and recommendations. If the LLM is unavailable, Kintsugi uses deterministic fallback text.

The result is a tool that is fast, explainable, privacy-conscious, and practical. It helps users avoid wasting a week training on a dataset that was never safe to train on in the first place.

## 22. Suggested Demo Walkthrough

1. Open the app and explain that Kintsugi is a dataset preflight check.
2. Upload a clean demo dataset and show the score.
3. Point out the integrity score, readiness score, and verdict.
4. Upload a messy dataset and show missingness, outliers, and feature-quality warnings.
5. Upload a leaky dataset and show the critical leakage finding.
6. Explain why leakage makes offline metrics misleading.
7. Show that Kintsugi provides fix snippets, not just warnings.
8. Show the executive summary.
9. Explain that the LLM summary is optional and uses computed diagnostics only.
10. Close with the value: fewer wasted experiments, safer modeling, clearer communication.

## 23. Methodology Summary

Kintsugi's methodology can be summarized as:

```text
Profile the dataset.
Classify its structure.
Run targeted diagnostics.
Represent issues as evidence-backed findings.
Score integrity and readiness separately.
Cap scores for severe ML failure modes.
Generate a report.
Use an LLM only for optional communication.
```

This is why Kintsugi is more than a GPT wrapper. The intelligence is in the diagnostic architecture and scoring methodology. The LLM is only the narrator.

