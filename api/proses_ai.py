"""GET /api/proses_ai?input=<data> — RF + SVM paralel (asyncio.gather) + analisis naratif NVIDIA NIM."""
import asyncio, json, math, os, re, time
from pathlib import Path

import httpx
from fastapi import FastAPI, Query

app = FastAPI()
M = json.loads((Path(__file__).parent / "model.json").read_text())
NIM_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
NIM_MODEL = os.getenv("NIM_MODEL", "nvidia/nemotron-3.5-lightning-30b-a3b")
DEFAULT = [round(m, 2) for m in M["scaler"]["mean"]]  # rata-rata data latih


def parse(raw: str):
    try:
        v = [float(x) for x in raw.split(",")]
        if len(v) == len(M["features"]):
            return v
    except ValueError:
        pass
    return DEFAULT


def dua_status(label: str) -> str:
    """Sederhanakan kelas model jadi dua status: Aman atau Bahaya."""
    return "Aman" if re.search(r"aman|normal", label, re.I) else "Bahaya"


def scale(x):
    return [(a - m) / s for a, m, s in zip(x, M["scaler"]["mean"], M["scaler"]["scale"])]


def rf_predict(x):
    votes = [0.0] * len(M["classes"])
    for t in M["rf"]:
        n = 0
        while t["l"][n] != -1:
            n = t["l"][n] if x[t["f"][n]] <= t["t"][n] else t["r"][n]
        dist = t["v"][n]
        tot = sum(dist) or 1
        votes = [a + b / tot for a, b in zip(votes, dist)]
    i = max(range(len(votes)), key=votes.__getitem__)
    return dua_status(M["classes"][i]), votes[i] / len(M["rf"])


def svm_predict(x):
    scores = [sum(c * f for c, f in zip(w, x)) + b for w, b in zip(M["svm"]["coef"], M["svm"]["intercept"])]
    i = max(range(len(scores)), key=scores.__getitem__)
    exps = [math.exp(v - scores[i]) for v in scores]  # softmax skor margin -> confidence
    return dua_status(M["classes"][i]), scores[i], exps[i] / sum(exps)


async def run_rf(x):
    t0 = time.perf_counter()
    await asyncio.sleep(0.3)  # simulasi latensi inferensi RF
    label, conf = rf_predict(x)
    return {"model": "Random Forest", "prediksi": label, "confidence": round(conf, 3),
            "f1_test": M["metrics"]["rf_f1"], "durasi": round(time.perf_counter() - t0, 3)}


async def run_svm(x):
    t0 = time.perf_counter()
    await asyncio.sleep(0.5)  # simulasi latensi inferensi SVM
    label, score, conf = svm_predict(x)
    return {"model": "SVM", "prediksi": label, "skor": round(score, 3), "confidence": round(conf, 3),
            "f1_test": M["metrics"]["svm_f1"], "durasi": round(time.perf_counter() - t0, 3)}


async def run_nim(raw, x):
    key = os.getenv("NVIDIA_API_KEY")
    if not key:
        return {"aktif": False, "pesan": "NVIDIA_API_KEY belum diset"}
    prompt = (f"Data indikator keamanan: {dict(zip(M['features'], x))}. Konteks: {raw}. "
              f"Beri analisis ancaman singkat 1-2 kalimat bahasa Indonesia, akhiri dengan kategori: Aman/Bahaya.")
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(NIM_URL, headers={"Authorization": f"Bearer {key}"},
                             json={"model": NIM_MODEL, "max_tokens": 400, "temperature": 0.2,
                                   "chat_template_kwargs": {"enable_thinking": False},
                                   "messages": [{"role": "system", "content": "/no_think"}, {"role": "user", "content": prompt}]})
            r.raise_for_status()
            teks = r.json()["choices"][0]["message"]["content"].strip()
            return {"aktif": True, "model": NIM_MODEL, "analisis": teks,
                    "kategori": "Bahaya" if re.search(r"bahaya", teks, re.I) else "Aman"}
    except Exception as e:
        return {"aktif": False, "pesan": f"NIM error: {e}"}


@app.get("/api/proses_ai")
async def proses_ai(input: str = Query(default=""), nim: int = 0):
    x_raw = parse(input)
    x = scale(x_raw)
    t0 = time.perf_counter()
    rf, svm = await asyncio.gather(run_rf(x), run_svm(x))
    duration = round(time.perf_counter() - t0, 3)
    hasil = {"status": "success", "mode": "async-parallel", "input": dict(zip(M["features"], x_raw)),
             "duration_seconds": duration, "sequential_estimate": round(rf["durasi"] + svm["durasi"], 3),
             "rf": rf, "svm": svm,
             "rekomendasi_produksi": "SVM" if M["metrics"]["svm_f1"] >= M["metrics"]["rf_f1"] else "Random Forest"}
    if nim:
        hasil["nvidia_nim"] = await run_nim(input, x_raw)
    return hasil
