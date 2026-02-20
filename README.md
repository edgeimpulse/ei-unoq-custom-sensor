Option A (recommended): sample + infer on the MCU (Arduino sketch)

This avoids bandwidth problems and service conflicts. At 44.1 kHz:

int16 stream bandwidth = 44100 * 2 ≈ 88 kB/s (fine)

but if you try to push that through low baud links or via router services, it becomes brittle.

If you want, I’ll give you a “full” MCU inference sketch (ADC → ring buffer → run_classifier()), but you asked specifically about Linux runner, so here’s the streaming variant first.

Option B: MCU samples A0, streams to Linux, Python runs Edge Impulse inference
Critical UNO Q plumbing detail (Linux↔MCU link)

On UNO Q, the Linux processor and MCU are connected internally (UART/SPI). The Arduino router/bridge services typically claim the UART by default, so you may need to stop them to use the raw link. One common mapping reported is:

Linux side: /dev/ttyHS1

MCU side: Serial1

…and stopping arduino-router can free it (but will conflict with App Lab / Bridge workflows).

B1) MCU Arduino sketch: 44.1 kHz sample A0 and stream frames over Serial1

This sketch:

samples A0 at ~44.1 kHz (fixed-point micros scheduler)

packs samples into binary frames

sends over Serial1 at 2,000,000 baud (you can adjust)

/*
  UNO Q (MCU) - 44.1 kHz ADC sampling on A0 -> stream to Linux over Serial1

  Transport:
    Serial1 @ 2,000,000 baud (adjust as needed)

  Frame format (little-endian):
    uint16  MAGIC = 0xA55A
    uint32  seq
    uint16  nsamp
    int16   samples[nsamp]
    uint16  crc16_ccitt (over MAGIC..samples)

  Notes:
  - You will likely need to stop Arduino router services on Linux to use /dev/ttyHS1.
  - Avoid printing in the sampling loop; it will destroy timing.
*/

#include <Arduino.h>

static constexpr uint32_t SAMPLE_RATE_HZ = 44100;
static constexpr uint32_t BAUD = 2000000;

// Number of samples per transmitted frame
static constexpr uint16_t FRAME_SAMPLES = 512;

// ADC config
static constexpr uint8_t ANALOG_PIN = A0;

// Scheduler (fixed-point for 44.1k: 22 + remainder)
static constexpr uint32_t ONE_MILLION = 1000000;
static constexpr uint32_t PERIOD_US = ONE_MILLION / SAMPLE_RATE_HZ;   // 22
static constexpr uint32_t REM_US_NUM = ONE_MILLION % SAMPLE_RATE_HZ;  // 29800
static uint32_t rem_accum = 0;

// Sample buffer for one frame
static int16_t frame_buf[FRAME_SAMPLES];
static uint16_t frame_idx = 0;
static uint32_t seq = 0;

static inline bool time_reached(uint32_t now, uint32_t target) {
  return (int32_t)(now - target) >= 0;
}

// CRC16-CCITT (0x1021), init 0xFFFF
static uint16_t crc16_ccitt(const uint8_t *data, size_t len) {
  uint16_t crc = 0xFFFF;
  for (size_t i = 0; i < len; i++) {
    crc ^= (uint16_t)data[i] << 8;
    for (uint8_t b = 0; b < 8; b++) {
      if (crc & 0x8000) crc = (crc << 1) ^ 0x1021;
      else crc <<= 1;
    }
  }
  return crc;
}

static void send_frame(const int16_t *samples, uint16_t nsamp, uint32_t seqno) {
  # ei-unoq-custom-sensor

  # ei-unoq-custom-sensor

  A tiny example repo for streaming raw ADC samples from an UNO Q MCU to Linux and running an Edge Impulse `.eim` model on the Linux side. Two approaches are provided:

  - Option A (recommended): run inference on the MCU (ADC → ring buffer → on-device classifier) and only send compact events to Linux.
  - Option B: stream framed ADC samples from MCU to Linux and run the Edge Impulse runner there.

  Files
  - `unoq_stream.ino` — Arduino sketch for UNO Q: samples A0 at 44.1 kHz and streams framed int16 samples over `Serial1`.
  - `unoq_adc_infer.py` — Python runner: reads frames from a serial device (e.g. `/dev/ttyHS1`) and classifies windows with an Edge Impulse `.eim` model.
  - `requirements.txt` — Python dependencies (`edge_impulse_linux`, `pyserial`, `numpy`).
  - `LICENSE` — MIT license.
  - `.gitignore` — ignores common Python/Arduino artifacts and `.eim` files.

  Quickstart (Linux)

  1. Stop any router/bridge that may claim the UART (if needed):

  ```bash
  sudo service arduino-router stop
  ```

  2. Install Python deps:

  ```bash
  python3 -m pip install --upgrade pip
  python3 -m pip install -r requirements.txt
  ```

  3. Download or copy your Edge Impulse model into the repo (example: `modelfile.eim`).

  4. Run the Python runner (example):

  ```bash
  python3 unoq_adc_infer.py --model modelfile.eim --port /dev/ttyHS1 --baud 2000000 \
    --frame-samples 512 --window-samples 11025 --center
  ```

  Protocol (streamed frames)

  Each frame sent from the MCU is little-endian and formatted as:

  - `uint16` MAGIC = `0xA55A`
  - `uint32` seq (frame sequence number)
  - `uint16` nsamp (number of int16 samples)
  - `int16[]` samples (nsamp values)
  - `uint16` crc16_ccitt (CRC over header+payload)

  Notes
  - Sampling: 44.1 kHz, 16-bit samples → ~88 kB/s raw stream. Streaming continuously can be brittle over lower baud rates or when other services claim the UART.
  - On UNO Q, the Linux processor and MCU are commonly mapped: Linux `/dev/ttyHS1` ↔ MCU `Serial1`.
  - Avoid `Serial.print` in the tight sampling loop on the MCU — it will break timing.
  - Adjust `FRAME_SAMPLES`, baud rate, and `window-samples` to match your model and link quality.

  License

  This project is licensed under the MIT License. See `LICENSE`.