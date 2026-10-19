"""Load locally trained, trusted artifacts only. No fitting in API requests."""
from pathlib import Path

import joblib
import numpy as np
import sklearn
from sklearn.pipeline import Pipeline


class ModelPredictor:
    def __init__(self, path: Path):
        bundle = joblib.load(path)  # Pickle format: only load artifacts you trained/trust.
        if not isinstance(bundle, dict) or bundle.get("format_version") != 1:
            raise ValueError("Unsupported model artifact format")
        self.pipeline = bundle["pipeline"]
        self.metadata = bundle["metadata"]
        if self.metadata["versions"]["scikit_learn"] != sklearn.__version__:
            raise ValueError("Model scikit-learn version differs; retrain using this environment")
        if not isinstance(self.pipeline, Pipeline) or list(self.pipeline.classes_) != [0, 1]:
            raise ValueError("Model must be a fitted binary pipeline with classes [0, 1]")

    def predict(self, text: str) -> dict:
        probabilities = self.pipeline.predict_proba([text])[0]
        probability = float(probabilities[list(self.pipeline.classes_).index(1)])
        if not np.isfinite(probability):
            raise ValueError("Non-finite model output")
        return {"status": "available", "label": "fraudulent" if probability >= 0.5 else "legitimate",
                "fraud_probability": probability, "threshold": 0.5,
                "model_version": "tfidf-logreg-" + self.metadata["dataset_sha256"][:12],
                "note": "Class-weighted model output; not a calibrated real-world fraud probability or a fraud verdict."}
