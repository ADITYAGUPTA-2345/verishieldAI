# Measured training results

These results were computed from the supplied local CSV, not generated labels or example metrics.

Dataset SHA-256: `59253295129d8b6a27607f9904f7d4ddf4dbb0ee35e079c7eb51b58b5e62bf60`

Raw rows: 17,880. Cleaned unique model inputs: 15,872.
Raw class distribution: legitimate 17,014; fraudulent 866.
Duplicate excess: full rows 0; excluding job ID 281; normalized combined text 2,008.
Conflicting normalized text groups: 0.

## Columns and missing values

| Column | Missing/blank rows |
| --- | ---: |
| job_id | 0 |
| title | 0 |
| location | 346 |
| department | 11,553 |
| salary_range | 15,012 |
| company_profile | 3,308 |
| description | 1 |
| requirements | 2,696 |
| benefits | 7,214 |
| telecommuting | 0 |
| has_company_logo | 0 |
| has_questions | 0 |
| employment_type | 3,471 |
| required_experience | 7,050 |
| required_education | 8,105 |
| industry | 4,903 |
| function | 6,455 |
| fraudulent | 0 |

## Holdout evaluation

Training: 12,741 rows (12,181 legitimate, 560 fraudulent).
Test: 3,131 rows (2,978 legitimate, 153 fraudulent).
Description groups and identical combined text do not overlap across splits.

| Metric | Measured value |
| --- | ---: |
| Accuracy | 97.5088% |
| Fraud precision | 74.5098% |
| Fraud recall | 74.5098% |
| Fraud F1 | 74.5098% |
| Always-legitimate baseline accuracy | 95.1134% |

Confusion matrix: rows actual, columns predicted.

| Actual / predicted | Legitimate | Fraudulent |
| --- | ---: | ---: |
| Legitimate | 2939 | 39 |
| Fraudulent | 39 | 114 |

Single historical holdout; not company-disjoint or temporal. Near-duplicates and shared templates may remain. Browser page text differs from curated dataset text. Balanced model probabilities are not calibrated fraud likelihoods.

See evaluation.json for exact floating-point metrics, class reports, versions, parameters, and model hash.
