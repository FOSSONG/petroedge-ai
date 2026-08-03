import pandas as pd
import joblib

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score,
    classification_report,
)

df = pd.read_csv(
    "data/niger_delta_synthetic.csv"
)

X = df[
    [
        "gamma_ray_api",
        "resistivity_ohmm",
        "density_gcc",
        "neutron_porosity_vv",
        "sonic_usft",
        "caliper_in"
    ]
]

y = df["lithology"]

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42,
    stratify=y
)


print(
    "Train shape:",
    X_train.shape
)

print(
    "Test shape:",
    X_test.shape
)

overlap = len(
    set(X_train.index)
    &
    set(X_test.index)
)

print(
    "Overlap:",
    overlap
)


model = RandomForestClassifier(
    n_estimators=200,
    random_state=42
)

model.fit(
    X_train,
    y_train
)

pred = model.predict(X_test)

from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix
)

accuracy = accuracy_score(
    y_test,
    pred
)

report = classification_report(
    y_test,
    pred
)

matrix = confusion_matrix(
    y_test,
    pred
)

print()
print("=" * 40)
print("LITHOLOGY MODEL PERFORMANCE")
print("=" * 40)

print(
    f"Accuracy : {accuracy:.4f}"
)

print()
print("Confusion Matrix")
print(matrix)

print()
print("Classification Report")
print(report)

joblib.dump(
    model,
    "models/lithology_rf.pkl"
)

with open(
    "models/lithology_metrics.txt",
    "w"
) as f:

    f.write(
        f"Accuracy: {accuracy:.4f}\n\n"
    )

    f.write(
        str(matrix)
    )

    f.write("\n\n")

    f.write(report)

print("Saved.")