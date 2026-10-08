"""Latih RF + SVM (linear) dari CSV, ekspor ke JSON agar inferensi di Vercel tanpa scikit-learn."""
import json, sys, time
from pathlib import Path
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.svm import LinearSVC
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import f1_score

ROOT = Path(__file__).resolve().parent.parent
FEATS = ["Frekuensi_Serangan_Siber", "Jumlah_Anomali_Lalu_Lintas_Data", "Sentimen_Media_Sosial_Lokal",
         "Kepadatan_Penduduk_Area", "Aktivitas_Enkripsi_Mencurigakan"]
LABEL = "Kategori_Ancaman"
CSV = sys.argv[1] if len(sys.argv) > 1 else "maritime_border_data.csv"
if len(sys.argv) > 2:  # opsional: daftar fitur dipisah koma
    FEATS = sys.argv[2].split(",")
if len(sys.argv) > 3:  # opsional: nama kolom label
    LABEL = sys.argv[3]

df = pd.read_csv(CSV, encoding="utf-8-sig")
for c in FEATS:  # bersihkan karakter non-numerik lalu jadikan angka
    if df[c].dtype == object:
        df[c] = pd.to_numeric(df[c].astype(str).str.replace(r"[^0-9.\-]", "", regex=True), errors="coerce")
df = df.dropna(subset=FEATS + [LABEL])
X, y = df[FEATS].astype(float), df[LABEL]
Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
sc = StandardScaler().fit(Xtr)

rf = RandomForestClassifier(n_estimators=30, max_depth=6, random_state=42).fit(sc.transform(Xtr), ytr)
svm = LinearSVC(random_state=42, max_iter=10000).fit(sc.transform(Xtr), ytr)

def tree_json(t):
    t = t.tree_
    return {"l": t.children_left.tolist(), "r": t.children_right.tolist(), "f": t.feature.tolist(),
            "t": [round(v, 6) for v in t.threshold.tolist()], "v": [v[0].tolist() for v in t.value]}

out = {
    "features": FEATS, "classes": rf.classes_.tolist(),
    "scaler": {"mean": sc.mean_.tolist(), "scale": sc.scale_.tolist()},
    "rf": [tree_json(e) for e in rf.estimators_],
    "svm": {"coef": svm.coef_.tolist(), "intercept": svm.intercept_.tolist()},
    "metrics": {
        "rf_f1": round(f1_score(yte, rf.predict(sc.transform(Xte)), average="macro"), 3),
        "svm_f1": round(f1_score(yte, svm.predict(sc.transform(Xte)), average="macro"), 3),
    },
}
json.dump(out, open(ROOT / "api" / "model.json", "w"))
print(out["classes"], out["metrics"])
