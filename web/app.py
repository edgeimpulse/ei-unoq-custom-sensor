from __future__ import annotations

import os
from pathlib import Path
from typing import List

from flask import Flask, jsonify, render_template, request, send_file, abort

app = Flask(__name__, template_folder="templates", static_folder="static")

# ---- Configure paths (adjust to your repo layout) ----
REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_DIR = REPO_ROOT / "samples"
MODELS_DIR = REPO_ROOT / "models"

# If you already compute/cache spectrograms somewhere:
CACHE_DIR = REPO_ROOT / ".cache"
CACHE_DIR.mkdir(exist_ok=True)


def list_wav_samples() -> List[str]:
    if not SAMPLES_DIR.exists():
        return []
    return sorted([p.name for p in SAMPLES_DIR.glob("*.wav")])


def list_models() -> List[str]:
    if not MODELS_DIR.exists():
        return []
    models = [p.name for p in MODELS_DIR.iterdir() if p.is_file()]
    return sorted(models)


@app.get("/health")
def health():
    return jsonify({"ok": True})


@app.get("/")
def index():
    samples = list_wav_samples()
    return render_template("index.html", samples=samples)


@app.get("/sample/<sample_name>")
def sample_page(sample_name: str):
    sample_path = SAMPLES_DIR / sample_name
    if not sample_path.exists():
        abort(404)

    models = list_models()
    default_model = request.args.get("model") or (models[0] if models else "")

    return render_template(
        "sample.html",
        sample_name=sample_name,
        models=models,
        default_model=default_model,
    )


@app.get("/api/sample/<sample_name>/meta")
def sample_meta(sample_name: str):
    sample_path = SAMPLES_DIR / sample_name
    if not sample_path.exists():
        abort(404)

    return jsonify({
        "sample": sample_name,
        "rate_hz": 4000,
        "duration_ms": 0,
    })


@app.get("/api/sample/<sample_name>/audio")
def sample_audio(sample_name: str):
    sample_path = SAMPLES_DIR / sample_name
    if not sample_path.exists():
        abort(404)
    return send_file(sample_path, mimetype="audio/wav")


@app.get("/api/sample/<sample_name>/spectrogram/noisy.png")
def noisy_spectrogram(sample_name: str):
    abort(404)


@app.get("/api/sample/<sample_name>/spectrogram/denoised.png")
def denoised_spectrogram(sample_name: str):
    abort(404)


@app.get("/api/sample/<sample_name>/spectrogram/zoom/noisy.png")
def zoom_noisy(sample_name: str):
    abort(404)


@app.get("/api/sample/<sample_name>/spectrogram/zoom/denoised.png")
def zoom_denoised(sample_name: str):
    abort(404)


@app.post("/api/sample/<sample_name>/denoise")
def denoise(sample_name: str):
    sample_path = SAMPLES_DIR / sample_name
    if not sample_path.exists():
        abort(404)

    payload = request.get_json(silent=True) or {}
    model = payload.get("model", "")
    zoom_start_s = float(payload.get("zoom_start_s", 0.0))
    zoom_len_s = float(payload.get("zoom_len_s", 1.0))

    # TODO: call your denoise pipeline here and write outputs into CACHE_DIR

    return jsonify({"ok": True})


@app.post("/api/sample/<sample_name>/reset_zoom")
def reset_zoom(sample_name: str):
    return jsonify({"ok": True})


@app.post("/api/sample/<sample_name>/erase_edits")
def erase_edits(sample_name: str):
    return jsonify({"ok": True})
