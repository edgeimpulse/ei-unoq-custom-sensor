# UNO Q Analog A0 @ 44.1 kHz → Linux Python → Edge Impulse (.eim)

This repo template captures **analog samples on the Arduino UNO Q MCU** (STM32U585, Arduino sketch) and streams them to the **UNO Q Linux side**, where a **Python script** feeds the samples into the **Edge Impulse Linux runner** using a `.eim` model.

> ⚠️ UNO Q plumbing note: the Linux processor and the MCU are connected internally. The Arduino router/bridge services commonly **claim the UART** by default, so you may need to stop them to use the raw serial link.
>
> A commonly reported mapping is:
> - Linux side: `/dev/ttyHS1`
> - MCU side: `Serial1`
>
> Stopping `arduino-router` can free the UART, but this can conflict with App Lab / Bridge workflows.



## Repo layout

- `arduino/uno_q_adc_streamer/uno_q_adc_streamer.ino`
  - Samples **A0** at **~44.1 kHz** (fixed-point micros scheduler)
  - Streams framed **int16** samples over `Serial1` (binary protocol)
- `linux/unoq_adc_infer.py`
  - Reads frames from a serial device (default `/dev/ttyHS1`)
  - Reassembles a window (e.g. **11025 samples** = 250 ms @ 44.1k)
  - Runs inference via `edge_impulse_linux.runner.ImpulseRunner` on a `.eim`
- `scripts/stop-router.sh` / `scripts/start-router.sh`
  - Convenience scripts to stop/start `arduino-router` (if it’s claiming the UART)
- `LICENSE`, `.gitignore`



## Hardware wiring

- Sensor output → `A0`
- Sensor GND → `GND`
- Sensor VCC → `3.3V`

**Keep the analog voltage within 0–3.3V.**  
If your signal is audio-like, you typically need a bias and an anti-alias filter.



## Option A vs Option B

### Option A (recommended)
Run inference on the **MCU** and only send compact results/events to Linux.
- Pros: best timing + least brittle
- Cons: you must deploy/run the EI library on MCU

### Option B (this repo)
Stream raw ADC samples MCU → Linux and run inference in Python on Linux.
- Pros: fastest iteration, easy logging, simple model swaps (`.eim`)
- Cons: continuous streaming can be brittle if the UART is shared or baud rate is too low



## MCU build / flash (Arduino IDE)

1. Open Arduino IDE
2. Select **Arduino UNO Q**
3. Open:
   - `arduino/uno_q_adc_streamer/uno_q_adc_streamer.ino`
4. Upload

Defaults in the sketch:
- `analogReadResolution(12)`
- `Serial1` at **2,000,000 baud**
- `FRAME_SAMPLES = 512`

> Tip: avoid adding any `Serial.print()` inside the sampling loop; printing will break timing.



## Linux setup (on UNO Q)

### 1) Install Python deps

```bash
python3 -m pip install --upgrade pip
python3 -m pip install edge_impulse_linux pyserial numpy
```
2) Download a model .eim

From your Edge Impulse project (on the UNO Q Linux side):

edge-impulse-linux-runner --download modelfile.eim

Or copy an existing .eim into the repo.

3) Free the UART device (if needed)

If /dev/ttyHS1 is busy:

sudo ./scripts/stop-router.sh

To restore later:

sudo ./scripts/start-router.sh
4) Run inference

Example for a 250 ms window (11025 samples @ 44.1 kHz):

python3 linux/unoq_adc_infer.py \
  --model modelfile.eim \
  --port /dev/ttyHS1 \
  --baud 2000000 \
  --frame-samples 512 \
  --window-samples 11025 \
  --adc-bits 12 \
  --center
Stream protocol (MCU → Linux)

Each frame sent by the MCU is little-endian:

uint16 MAGIC = 0xA55A

uint32 seq (frame sequence number)

uint16 nsamp (number of int16 samples)

int16[nsamp] samples (raw ADC codes from analogRead)

uint16 crc16_ccitt (CRC over header + payload)

The Python script:

resynchronizes by scanning for MAGIC

validates CRC16-CCITT

warns if seq jumps (drops/resync events)

Tuning
Window size must match your model

--window-samples must match the model input length. Common values at 44.1 kHz:

250 ms → 11025

500 ms → 22050

1000 ms → 44100

Normalization / centering

--center: maps ADC codes to [-1..1] (typical for audio-like raw signals)

without --center: maps ADC codes to [0..1]

ADC resolution

If you change analogReadResolution() in the sketch, update:

--adc-bits in the Python script

Link stability

If you see CRC mismatches or frequent seq jumps:

Increase baud rate (or reduce FRAME_SAMPLES)

Ensure arduino-router isn’t sharing the UART

Reduce Linux load while testing
