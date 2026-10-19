# Machine learning methodology

## Dataset and license

Training uses the actual local `ml/data/fake_job_postings.csv`, never a generated substitute or fake labels. Download the original [Real / Fake Job Posting Prediction](https://www.kaggle.com/datasets/shivamb/real-or-fake-fake-jobposting-prediction) CSV published by Shivam Bansal. The data card acknowledges the University of the Aegean's Laboratory of Information & Communication Systems Security and lists **CC0: Public Domain**. This was checked against Kaggle's data card and public dataset metadata on 19 October 2026. See [third-party notices](../THIRD_PARTY_NOTICES.md).

The CSV/model are local-only ignored artifacts, not part of the source release. Do not use a balanced synthetic mirror to reproduce these results.

## Inspection before fitting

The original CSV has 17,880 rows and 18 columns. Label 0 has 17,014 rows and label 1 has 866. There are no missing labels, no exact full-row duplicate excess, 281 duplicate excess records excluding job_id, 2,008 duplicate normalized combined texts, and no conflicting labels within those combined-text groups. Missing examples: description 1, company_profile 3,308, requirements 2,696, benefits 7,214. Every column's missing count is in [dataset_inspection.json](../ml/reports/dataset_inspection.json).

Dataset SHA-256:

```text
59253295129d8b6a27607f9904f7d4ddf4dbb0ee35e079c7eb51b58b5e62bf60
```

## Preprocessing and target isolation

- Features combine title, company_profile, description, requirements and benefits.
- Missing text is empty; HTML tags/entities, whitespace and case are normalized through shared importable preprocessing.
- Missing/invalid labels are rejected, not imputed. Malformed rows, missing required columns and conflicting labels for identical normalized model inputs fail validation.
- Empty model inputs are excluded. Identical normalized combined texts are deduplicated before splitting.
- fraudulent, job_id and structured metadata are never features. URLs are not fetched/scored by the classifier.
- After cleaning: 15,872 unique model inputs, 15,159 legitimate and 713 fraudulent, across 14,592 normalized-description groups.

## Split and leakage controls

The predetermined first fold of `StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)` is the holdout. It attempts class stratification while preventing identical normalized descriptions from crossing train/test, even when other fields differ. Original CSV row numbers are recorded in [split_manifest.json](../ml/reports/split_manifest.json).

| Split | Legitimate | Fraudulent | Total |
| --- | ---: | ---: | ---: |
| Train | 12,181 | 560 | 12,741 |
| Test | 2,978 | 153 | 3,131 |

The split has zero normalized-description group overlap and zero identical combined-text overlap. Vocabulary, IDF and balanced class weights are fitted only on training rows. The holdout is not used to select hyperparameters or tune the preset 0.5 threshold. The saved pipeline is not refitted on the test set. Tests recompute metrics for verification without refitting/tuning.

## Estimator and imbalance

| Component | Fixed configuration |
| --- | --- |
| TF-IDF | word unigrams/bigrams; min_df=2; max_features=60000; sublinear_tf=True |
| Logistic Regression | solver=liblinear; C=1.0; class_weight=balanced; max_iter=1000; random_state=42 |
| Positive class | fraudulent=1 |
| Decision threshold | 0.5 |

Balanced weights are learned from training class counts. No oversampling or synthetic records are used. Training fails on convergence warnings. Joblib saves the entire fitted pipeline with format version, dataset checksum, parameters and environment metadata.

## Actual holdout metrics

| Metric | Exact reported value | Rounded |
| --- | ---: | ---: |
| Accuracy | 0.9750878313637815 | 97.51% |
| Fraud precision | 0.7450980392156863 | 74.51% |
| Fraud recall | 0.7450980392156863 | 74.51% |
| Fraud F1 | 0.7450980392156863 | 74.51% |
| Majority baseline accuracy | 0.9511338230597254 | 95.11% |

Rows actual, columns predicted, order [legitimate, fraudulent]:

```text
[[2939, 39],
 [  39,114]]
```

There are 39 missed fraudulent postings and 39 false alarms in this holdout. [evaluation.json](../ml/reports/evaluation.json) includes per-class, macro and weighted metrics, versions and artifact hash. These values were computed from this CSV; they are not demo predictions.

## Reproduce on Windows

From the repository root, after placing the original CSV:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m ml.train
.\.venv\Scripts\python.exe -m pytest backend/tests ml/tests -q
```

Skip venv creation when already installed. Default training outputs overwrite the local model/reports; skip training if preserving an existing artifact, or specify isolated outputs:

```powershell
.\.venv\Scripts\python.exe -m ml.train --artifact ml/artifacts/retrained.joblib --reports ml/reports/retrained
```

The original recorded environment is Python 3.12.3, scikit-learn 1.7.2, NumPy 2.2.6, SciPy 1.15.3, and Joblib 1.5.2. The lock file is the recommended inference/training environment. Saved model compatibility across scikit-learn versions is not supported; only load trusted Joblib files. See [scikit-learn persistence guidance](https://scikit-learn.org/stable/model_persistence.html).

## Inference and limitations

FastAPI combines optional page title and submitted page text and calls the loaded pipeline. Rule findings and probability remain separate. The local evidence-retrieval vectorizer never changes this model.

The historical holdout is neither temporal nor company-disjoint. Similar templates/company profiles can remain despite exact-description grouping. Browser text differs from curated dataset fields, and no current live-page accuracy has been measured. Balanced-model output is uncalibrated; a low probability is not proof of legitimacy. Calibration, robust fresh-data evaluation and stronger group-based benchmarks are future work, not completed features.
