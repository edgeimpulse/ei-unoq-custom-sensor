# UNO Q Analog A0 @ 44.1 kHz → Linux Python → Edge Impulse (.eim)

This repo captures analog samples on the Arduino UNO Q MCU (STM32U585) and streams them to the UNO Q Linux side, where a Python script feeds the samples into the Edge Impulse Linux runner using a `.eim` model.

> ⚠️ UNO Q plumbing note: the Linux processor and the MCU are connected internally. The Arduino router/bridge services commonly claim the UART by default, so you may need to stop them to use the raw serial link.
>
> Common mapping:
> - Linux side: `/dev/ttyHS1`
> - MCU side: `Serial1`
>
> Stopping `arduino-router` can free the UART but may conflict with App Lab / Bridge workflows.


## Repo layout

- `arduino/uno_q_adc_streamer/uno_q_adc_streamer.ino`
  - Samples **A0** at ~**44.1 kHz** (fixed-point `micros()` scheduler)
  - Streams framed **int16** samples over `Serial1` (binary protocol)
- `linux/unoq_adc_infer.py`
  - Reads frames from a serial device (default `/dev/ttyHS1`)
  - Reassembles a window (e.g. **11025 samples** = 250 ms @ 44.1 kHz)
  - Runs inference via `edge_impulse_linux.runner.ImpulseRunner` on a `.eim`
- `scripts/stop-router.sh` / `scripts/start-router.sh`
  - Convenience scripts to stop/start `arduino-router`
- `LICENSE`, `.gitignore`


## Hardware wiring

- Sensor output → `A0`
- Sensor GND → `GND`
- Sensor VCC → `3.3V`

Keep the analog voltage within 0–3.3V. If your signal is audio-like, you typically need a DC bias and an anti-alias filter.


## Option A vs Option B

### Option A (recommended)
Run inference on the MCU and only send compact results/events to Linux.

- Pros: best timing, least brittle
- Cons: requires deploying the EI library on MCU

### Option B (this repo)
Stream raw ADC samples MCU → Linux and run inference in Python on Linux.

- Pros: fast iteration, easy logging, simple model swaps (`.eim`)
- Cons: continuous streaming can be brittle if the UART is shared or baud is too low


## MCU build / flash (Arduino IDE)

1. Open Arduino IDE
2. Select **Arduino UNO Q**
3. Open `arduino/uno_q_adc_streamer/uno_q_adc_streamer.ino`
4. Upload

Defaults in the sketch:

- `analogReadResolution(12)`
- `Serial1` at **2,000,000 baud**
- `FRAME_SAMPLES = 512`

> Tip: avoid `Serial.print()` inside the sampling loop; printing will break timing.


## Linux setup (on UNO Q)

### 1) Install Python deps

```bash
python3 -m pip install --upgrade pip
python3 -m pip install edge_impulse_linux pyserial numpy
```

### 2) Download a model `.eim`

From your Edge Impulse project on the UNO Q Linux side:

```bash
edge-impulse-linux-runner --download modelfile.eim
```

Or copy an existing `.eim` into the repo.

# UNO Q Custom Analogue Sensor Example
## MCU (ADC) ➜ Linux (Python) ➜ Edge Impulse (.eim) ➜ Optional Web App Demo UI

This repository provides a copy/paste runnable demo for the UNO Q pipeline and an optional mobile-friendly web UI. The repo contains:

- `arduino/uno_q_adc_streamer/uno_q_adc_streamer.ino` — MCU ADC streamer (samples A0, streams frames via `Serial1`).
- `linux/unoq_adc_infer.py` — reader/infer script (reads serial frames and runs an Edge Impulse `.eim`).
- `web/` — optional Flask UI (templates + static JS/CSS + server `web/app.py`).
- `scripts/stop-router.sh` and `scripts/start-router.sh` — convenience scripts to free/restore the UNO Q UART if `arduino-router` is active.

Quick notes:

- Linux UART device commonly used for the MCU link: `/dev/ttyHS1` (Linux side). The MCU exposes `Serial1`.
- If `arduino-router` holds the UART you'll need to stop it before using the serial link.

---

## MCU (Arduino) flash

Open the Arduino IDE, select the `Arduino UNO Q` board, open `arduino/uno_q_adc_streamer/uno_q_adc_streamer.ino` and upload.

Defaults in the sketch:

- `analogReadResolution(12)`
- `Serial1` at `2000000` baud
- `FRAME_SAMPLES = 512`

Avoid `Serial.print()` inside the sampling loop — it will break timing.

---

## Linux setup (UNO Q Linux side)

1) Install system deps and create a Python venv (single copy/paste block):

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip build-essential portaudio19-dev python3-dev

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

2) Get or place an Edge Impulse `.eim` model into the repo (e.g. copy into repo root or `models/`).

If you prefer to download on-device with the Edge Impulse runner:

```bash
edge-impulse-linux-runner --download modelfile.eim
```

3) If `/dev/ttyHS1` is claimed by `arduino-router`, free it before running your reader:

```bash
sudo ./scripts/stop-router.sh
# ... when you want it back:
sudo ./scripts/start-router.sh
```

4) Run the serial reader / inference (example):

```bash
source .venv/bin/activate

python3 linux/unoq_adc_infer.py \
  --model modelfile.eim \
  --port /dev/ttyHS1 \
  --baud 2000000 \
  --frame-samples 512 \
  --window-samples 11025 \
  --adc-bits 12 \
  --center
```

Notes:

- `--window-samples` must match your model input length (e.g. 11025 for 250 ms @ 44.1 kHz).
- `--center` maps ADC codes to [-1..1] (typical for audio-like signals). Omit to map to [0..1].
- If you change `analogReadResolution()` in the sketch, update `--adc-bits` accordingly.

---

## Web demo (optional)

If you added the `web/` folder and templates, start the Flask demo server from repo root:

```bash
source .venv/bin/activate
./run_server.sh --host 0.0.0.0 --port 8080
```

Then open from your phone (same network):

http://<arduino-ip>:8080/

By default the UI expects the following API contract implemented in `web/app.py`:

- `GET /` — samples list
- `GET /sample/<name>` — sample page
- `GET /api/sample/<name>/meta` — JSON metadata
- `GET /api/sample/<name>/audio` — WAV audio stream
- `GET /api/sample/<name>/spectrogram/noisy.png` — noisy spectrogram image
- `GET /api/sample/<name>/spectrogram/denoised.png` — denoised spectrogram image
- `GET /api/sample/<name>/spectrogram/zoom/*` — zoomed spectrogram images
- `POST /api/sample/<name>/denoise` — trigger denoise (JSON payload)
- `POST /api/sample/<name>/reset_zoom` — reset zoom state
- `POST /api/sample/<name>/erase_edits` — erase denoise outputs

The repository includes a minimal Flask server and a vanilla-JS UI that implements the UX hardening described earlier (busy state, toast, reset/erase split, model hint, connection badge). Endpoints for spectrogram and denoise are stubs — wire them to your existing pipeline so the UI can fetch PNGs and audio.

---

## Helpful scripts

- [scripts/stop-router.sh](scripts/stop-router.sh) — attempts to stop `arduino-router` or kill a running process of that name.
- [scripts/start-router.sh](scripts/start-router.sh) — attempts to start the service again.
- [run_server.sh](run_server.sh) — starts the Flask web server (activates `.venv` if present).