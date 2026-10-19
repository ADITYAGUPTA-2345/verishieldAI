# Third-party licenses and attribution

Reviewed on 19 October 2026 before selecting MIT for original project code/documentation. The public source tree declares external dependencies; it does not vendor their source, wheels, virtual environment, CSV, or trained model. MIT does not relicense those separate materials.

## External training data

- Publisher: Shivam Bansal; Real / Fake Job Posting Prediction.
- Source/data card: https://www.kaggle.com/datasets/shivamb/real-or-fake-fake-jobposting-prediction
- Publisher license: **CC0: Public Domain**, checked against the official Kaggle data card and public dataset-list metadata.
- Primary license listing: https://www.kaggle.com/shivamb/real-or-fake-fake-jobposting-prediction/kernels
- The data card acknowledges the University of the Aegean, Laboratory of Information & Communication Systems Security, and EMSCAD.
- CC0 legal text: https://creativecommons.org/publicdomain/zero/1.0/legalcode
- The local original CSV has SHA-256 59253295129d8b6a27607f9904f7d4ddf4dbb0ee35e079c7eb51b58b5e62bf60. It is not redistributed here. Keep provenance with any separately redistributed data/model; a dataset license does not authenticate the postings or remove privacy/third-party-content considerations.

## Locked Python packages

The following entries were checked against installed distribution metadata and, where needed, license files. This is an inventory, not replacement license text. Upstream packages retain their copyright, attribution, disclaimer and notice obligations.

| Package | Pinned version | Declared/reviewed license |
| --- | --- | --- |
| annotated-doc | 0.0.5 | MIT |
| annotated-types | 0.8.0 | MIT |
| anyio | 4.15.1 | MIT |
| certifi | 2026.10.18 | MPL-2.0 |
| charset-normalizer | 3.5.2 | MIT |
| click | 8.5.0 | BSD-3-Clause |
| colorama | 0.4.6 | BSD-3-Clause |
| fastapi | 0.148.0 | MIT |
| filelock | 4.2.4 | MIT |
| h11 | 0.16.0 | MIT |
| httpcore | 1.0.9 | BSD-3-Clause |
| httpx | 0.28.1 | BSD-3-Clause |
| idna | 3.20 | BSD-3-Clause |
| iniconfig | 2.3.1 | MIT |
| joblib | 1.5.2 | BSD-3-Clause; bundled vendored-component notices |
| numpy | 2.2.6 | BSD-3-Clause; bundled third-party notices in wheel LICENSE.txt |
| opentelemetry-api | 1.45.1 | Apache-2.0 |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause |
| pluggy | 1.7.0 | MIT |
| pydantic | 2.14.1 | MIT |
| pydantic_core | 2.50.1 | MIT |
| Pygments | 2.21.0 | BSD-2-Clause |
| pytest | 8.4.2 | MIT |
| python-dotenv | 1.2.4 | BSD-3-Clause |
| requests | 2.34.2 | Apache-2.0 |
| requests-file | 3.0.1 | Apache-2.0 |
| scikit-learn | 1.7.2 | BSD-3-Clause |
| scipy | 1.15.3 | BSD-3-Clause; bundled third-party notices in wheel LICENSE.txt |
| starlette | 1.9.0 | BSD-3-Clause |
| threadpoolctl | 3.7.0 | BSD-3-Clause |
| tldextract | 5.3.0 | BSD-3-Clause |
| typing-inspection | 0.4.4 | MIT |
| typing_extensions | 4.16.0 | PSF-2.0 |
| urllib3 | 2.8.0 | MIT |
| uvicorn | 0.54.0 | BSD-3-Clause |

## Bundled resources and distribution obligations

- tldextract itself is BSD-3-Clause; its installed Public Suffix List snapshot explicitly carries **MPL-2.0**. The app uses that upstream snapshot offline and does not copy it into this source repository.
- certifi carries **MPL-2.0** terms for its certificate data/distribution.
- Apache-2.0 components retain their LICENSE/NOTICE requirements. Requests includes a NOTICE file; packaging offers Apache-2.0 OR BSD-2-Clause.
- NumPy/SciPy binary wheels include additional upstream libraries/notices; joblib also includes vendored-component notices. Do not describe an entire redistributed Python environment as MIT-only.
- If publishing packaged executables, containers, modified dependency files, or wheels later, retain all relevant upstream license/notice texts and satisfy applicable source-availability/file-level obligations. That packaging is not part of this source-only submission.

## Services and fetched pages

TinyFish is used through its remote APIs, without bundling its SDK. API/service access remains governed by TinyFish account and service terms. This project does not claim endorsement or ownership of TinyFish, Chrome, employer names, or external platform content.

Fetched public web text, logos and future screenshots retain their owners' rights. Live receipt JSON files and credentials are ignored. Source links and small factual descriptions in the docs are not a license to republish whole web pages. Redact personal data and secrets before adding demo assets.

## Original source license

The MIT license in LICENSE applies to original VeriShield code and documentation contributed with the right to license it. It does not supersede the external dataset license, dependency licenses, service terms, or rights in fetched content. New contributions/assets must be checked for compatible provenance before publication.
