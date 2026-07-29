import pandas as pd
import joblib

from xgboost import XGBClassifier

from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    confusion_matrix,
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
        "caliper_in",
    ]
]

y = df["hydrocarbon"]

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=42,
    stratify=y,
)

model = XGBClassifier(
    n_estimators=200,
    max_depth=6,
    learning_rate=0.05,
    eval_metric="logloss",
)

model.fit(
    X_train,
    y_train,
)

predictions = model.predict(
    X_test
)

from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score
)

report = classification_report(
    y_test,
    predictions
)



probabilities = model.predict_proba(
    X_test
)[:, 1]

accuracy = accuracy_score(
    y_test,
    predictions,
)

precision = precision_score(
    y_test,
    predictions,
)

recall = recall_score(
    y_test,
    predictions,
)

f1 = f1_score(
    y_test,
    predictions,
)

roc_auc = roc_auc_score(
    y_test,
    probabilities,
)

cm = confusion_matrix(
    y_test,
    predictions,
)

print()
print("=================================")
print("HYDROCARBON MODEL PERFORMANCE")
print("=================================")

print(f"Accuracy  : {accuracy:.4f}")
print(f"Precision : {precision:.4f}")
print(f"Recall    : {recall:.4f}")
print(f"F1 Score  : {f1:.4f}")
print(f"ROC AUC   : {roc_auc:.4f}")

print()
print("Confusion Matrix")
print(cm)

print()
print("Classification Report")
print(
    classification_report(
        y_test,
        predictions
    )
)

importance = pd.DataFrame(
    {
        "Feature": X.columns,
        "Importance": model.feature_importances_,
    }
)

importance = importance.sort_values(
    by="Importance",
    ascending=False,
)

print()
print("Feature Importance")
print(importance)

joblib.dump(
    model,
    "models/hydrocarbon_xgb.pkl"
)

print("Model saved.")

print(df.head())

print(df["hydrocarbon"].value_counts())

with open(
    "models/hydrocarbon_metrics.txt",
    "w"
) as f:

    f.write("HYDROCARBON MODEL PERFORMANCE\n")
    f.write("=" * 40 + "\n")

    f.write(f"Accuracy  : {accuracy:.4f}\n")
    f.write(f"Precision : {precision:.4f}\n")
    f.write(f"Recall    : {recall:.4f}\n")
    f.write(f"F1 Score  : {f1:.4f}\n")
    f.write(f"ROC AUC   : {roc_auc:.4f}\n\n")

    f.write("Confusion Matrix\n")
    f.write(str(cm))
    f.write("\n\n")

    f.write("Classification Report\n")
    f.write(report)
    f.write("\n\n")


print(
    "\nMetrics saved to models/hydrocarbon_metrics.txt"
)