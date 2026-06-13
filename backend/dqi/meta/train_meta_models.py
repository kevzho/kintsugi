"""Optional meta-model trainer.

Training data is intentionally optional. The production analyzer uses
deterministic heuristics when these model files are absent.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from joblib import dump
from sklearn.ensemble import RandomForestClassifier


ROOT = Path(__file__).resolve().parent
LABELS = ROOT / "labels"
MODELS = ROOT / "models"


def _train(csv_name: str, target: str, out_name: str) -> bool:
    path = LABELS / csv_name
    if not path.exists():
        print(f"Skipping {csv_name}: missing labels")
        return False
    df = pd.read_csv(path)
    if target not in df.columns or len(df) < 20:
        print(f"Skipping {csv_name}: need >=20 rows and '{target}' column")
        return False
    y = df[target].astype(str)
    X = pd.get_dummies(df.drop(columns=[target]), dummy_na=True)
    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=8,
        class_weight="balanced",
        random_state=42,
    )
    model.fit(X, y)
    MODELS.mkdir(exist_ok=True)
    dump({"model": model, "columns": list(X.columns)}, MODELS / out_name)
    print(f"Wrote {out_name}")
    return True


def main() -> None:
    _train("column_training_data.csv", "role", "column_role_model.joblib")
    _train("dataset_training_data.csv", "dataset_type", "dataset_type_model.joblib")


if __name__ == "__main__":
    main()
