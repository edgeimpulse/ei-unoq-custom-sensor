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
  const uint16_t MAGIC = 0xA55A;

  // Build header in a small temp buffer
  uint8_t hdr[2 + 4 + 2];
  hdr[0] = (uint8_t)(MAGIC & 0xFF);
  hdr[1] = (uint8_t)(MAGIC >> 8);

  hdr[2] = (uint8_t)(seqno & 0xFF);
  hdr[3] = (uint8_t)((seqno >> 8) & 0xFF);
  hdr[4] = (uint8_t)((seqno >> 16) & 0xFF);
  hdr[5] = (uint8_t)((seqno >> 24) & 0xFF);

  hdr[6] = (uint8_t)(nsamp & 0xFF);
  hdr[7] = (uint8_t)(nsamp >> 8);

  // Build contiguous buffer: hdr + payload (nsamp*2)
  static uint8_t tx[sizeof(hdr) + FRAME_SAMPLES * 2 + 2];
  const size_t payload_bytes = (size_t)nsamp * 2;

  memcpy(tx, hdr, sizeof(hdr));
  memcpy(tx + sizeof(hdr), samples, payload_bytes);

  uint16_t crc2 = crc16_ccitt(tx, sizeof(hdr) + payload_bytes);

  tx[sizeof(hdr) + payload_bytes + 0] = (uint8_t)(crc2 & 0xFF);
  tx[sizeof(hdr) + payload_bytes + 1] = (uint8_t)(crc2 >> 8);

  Serial1.write(tx, sizeof(hdr) + payload_bytes + 2);
}

static inline void sample_once() {
  int v = analogRead(ANALOG_PIN);
  frame_buf[frame_idx++] = (int16_t)v;

  if (frame_idx >= FRAME_SAMPLES) {
    send_frame(frame_buf, FRAME_SAMPLES, seq++);
    frame_idx = 0;
  }
}

void setup() {
  analogReadResolution(12);

  Serial1.begin(BAUD);

  // Let link stabilize
  delay(100);
}

void loop() {
  static uint32_t next_t = micros();
  uint32_t now = micros();

  while (time_reached(now, next_t)) {
    sample_once();

    next_t += PERIOD_US;
    rem_accum += REM_US_NUM;
    if (rem_accum >= SAMPLE_RATE_HZ) {
      next_t += 1;
      rem_accum -= SAMPLE_RATE_HZ;
    }

    now = micros();
  }
}
