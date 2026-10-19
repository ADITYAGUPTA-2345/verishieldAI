# VeriShield AI machine learning

## Dataset and inspection

Use the original **Real / Fake Job Posting Prediction** dataset published by Shivam Bansal on Kaggle:
https://www.kaggle.com/datasets/shivamb/real-or-fake-fake-jobposting-prediction

Download and unzip it manually (Kaggle may require sign-in and acceptance of its terms), then put `fake_job_postings.csv` at `ml/data/fake_job_postings.csv`. The provided local CSV is used directly; this project never downloads a substitute or generates training records or labels. Dataset and model binaries are Git-ignored. Kaggle lists the dataset as CC0 Public Domain; see ../THIRD_PARTY_NOTICES.md for verified attribution and separate licensing. Keep that provenance with any redistribution.

`ml/reports/initial_inspection.json` records the initial read-only inspection. The training command regenerates `dataset_inspection.json`, including every column, missing-value counts, label distribution, duplicates, and dataset SHA-256. It fails on missing/invalid labels, conflicting labels for identical normalized model text, malformed CSV, or missing required text columns. Missing text values become empty strings. Empty combined texts are excluded. No target label is inferred or imputed.

## Windows commands

Run from the repository root with Python 3.12 (the tested locked environment):

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m ml.train
.\.venv\Scripts\python.exe -m pytest backend/tests ml/tests -q
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

If the virtual environment already exists, skip creating it. For the exact environment used in this run, install `requirements-lock.txt` instead of `requirements.txt`. Train before starting the server, or restart after training: the artifact is loaded once at startup, never fitted inside a request.

Optional CLI arguments:

```powershell
.\.venv\Scripts\python.exe -m ml.train --data ml/data/fake_job_postings.csv --artifact ml/artifacts/job_classifier.joblib --reports ml/reports
```

Outputs:

- `ml/artifacts/job_classifier.joblib`: complete fitted TF-IDF and Logistic Regression pipeline, plus model provenance and versions.
- `ml/reports/dataset_inspection.json`: dataset audit and cleaning counts.
- `ml/reports/evaluation.json`: actual untouched-holdout metrics, full per-class report, confusion matrix, majority-class baseline, versions, parameters, and artifact hash.
- `ml/reports/split_manifest.json`: original CSV row numbers for train/test (header is row 1), enabling an audit against the source file.

## Features, splitting, and imbalance

The model uses the combined `title`, `company_profile`, `description`, `requirements`, and `benefits` text. HTML tags/entities, whitespace, and case are normalized by the same importable function stored in the pipeline. The target `fraudulent` and `job_id` are never features; structured metadata such as logo flags is also excluded because the extension submits plain text.

Identical normalized combined text is deduplicated before splitting. Rows with the same normalized description are assigned a common group even when titles or other fields differ. The first fold of `StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)` is the approximately 20% holdout. It attempts class stratification while keeping description groups disjoint. Exact fold sizes and class counts are reported, since group sizes can prevent an exact 80/20 ratio. Both splits must contain both labels. A fixed seed, fixed first fold, pinned packages, source checksum, and source-row manifest make the experiment reproducible in the same environment.

TF-IDF uses unigrams and bigrams, `min_df=2`, at most 60,000 features, and sublinear term frequency. Logistic Regression uses `solver=liblinear`, `C=1`, `class_weight=balanced`, `max_iter=1000`, and seed 42. Only training data is passed to `fit`: vocabulary, IDF, and inverse-frequency class weights never see test rows. No oversampling or synthetic records are used. Convergence warnings fail training instead of silently saving an unconverged model.

The holdout is evaluated once using a preset 0.5 decision threshold, with no parameter selection based on holdout performance. The saved pipeline remains the one fitted on the training split; it is not refitted on holdout data. Tests may recompute metrics to verify the report but do not tune or refit the model. Any future tuning needs inner cross-validation within training data and a new untouched test set for a fresh performance claim.

## Metrics and limits

The positive class is `fraudulent=1`; `0` means legitimate according to the dataset labels. Evaluation includes accuracy, fraudulent-class precision/recall/F1, both classes' metrics, macro/weighted averages, and a confusion matrix with rows = actual and columns = predicted, ordered `[legitimate, fraudulent]`:

```text
[[true negatives, false positives],
 [false negatives, true positives]]
```

Accuracy alone is misleading with this imbalanced dataset, so compare it with the majority baseline and fraud recall/F1. Balanced class weights emphasize minority examples but the resulting `predict_proba` output is not calibrated to real-world fraud prevalence. It is not certainty or a fraud verdict.

This is a single historical holdout, not a temporal or company-disjoint benchmark. Identical descriptions cannot cross splits, but near-duplicate templates, related employers, and overlapping company profiles can remain. Browser text includes navigation and may omit fields or contain repeated titles; its distribution differs from curated CSV records. Independently labeled current page data is needed before making production effectiveness claims.

## FastAPI and extension behavior

`POST /analyze` returns the existing `risk_score`, `risk_level`, and `findings` from rules unchanged, and adds a separate `ml_prediction` object with `status`, `label`, `fraud_probability`, `threshold`, `model_version`, and `note`. The optional page title and visible text are combined for model input. URL is never fetched or used as a model feature. Rule points and ML probability are never added together.

If the artifact is missing, corrupt, incompatible, or inference fails, the API explicitly reports `ml_prediction.status=unavailable`, with no made-up label or probability. Rule screening and `/health` still work; `/health` means the HTTP service is alive, not that a model is loaded. The extension displays ML output separately under its own heading. Reload the extension in `chrome://extensions` after updating it.

The default path is `ml/artifacts/job_classifier.joblib`; `.env` may override it with `VERISHIELD_MODEL_PATH` (use an absolute path). Joblib uses pickle: load only artifacts you trained or otherwise trust. The loader requires the same scikit-learn version. Use the locked dependency versions when serving the model; cross-version persistence is unsupported by scikit-learn.

Technical references: [balanced Logistic Regression](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LogisticRegression.html), [grouped cross-validation](https://scikit-learn.org/stable/modules/cross_validation.html), and [model persistence](https://scikit-learn.org/stable/model_persistence.html).
