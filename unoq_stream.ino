/*
  UNO Q (MCU) - 44.1 kHz ADC sampling on A0 -> stream to Linux over Serial1

  Fix: decouple sampling from Serial1.write so TX blocking doesn't destroy sampling timing.

  Transport: Serial1 @ 2,000,000 baud (adjust as needed)

  Frame format (little-endian):
    uint16  MAGIC = 0xA55A
    uint32  seq
    uint16  nsamp
    int16   samples[nsamp]   (ADC codes)
    uint16  crc16_ccitt      (CRC over MAGIC..samples)
*/

#include <Arduino.h>
#include <string.h>

static constexpr uint32_t SAMPLE_RATE_HZ = 44100;
static constexpr uint32_t BAUD = 2000000;
static constexpr uint16_t FRAME_SAMPLES = 512;
static constexpr uint8_t ANALOG_PIN = A0;

static constexpr uint32_t ONE_MILLION = 1000000;
static constexpr uint32_t PERIOD_US = ONE_MILLION / SAMPLE_RATE_HZ;      // 22
static constexpr uint32_t REM_US_NUM = ONE_MILLION % SAMPLE_RATE_HZ;     // 29800
static uint32_t rem_accum = 0;

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

// Double buffers for sampling
static int16_t bufA[FRAME_SAMPLES];
static int16_t bufB[FRAME_SAMPLES];
static volatile bool bufA_ready = false;
static volatile bool bufB_ready = false;
static uint16_t idx = 0;
static bool useA = true;
static uint32_t seq = 0;

static void build_and_send_frame(const int16_t *samples, uint16_t nsamp, uint32_t seqno) {
  const uint16_t MAGIC = 0xA55A;

  uint8_t hdr[2 + 4 + 2];
  hdr[0] = (uint8_t)(MAGIC & 0xFF);
  hdr[1] = (uint8_t)(MAGIC >> 8);
  hdr[2] = (uint8_t)(seqno & 0xFF);
  hdr[3] = (uint8_t)((seqno >> 8) & 0xFF);
  hdr[4] = (uint8_t)((seqno >> 16) & 0xFF);
  hdr[5] = (uint8_t)((seqno >> 24) & 0xFF);
  hdr[6] = (uint8_t)(nsamp & 0xFF);
  hdr[7] = (uint8_t)(nsamp >> 8);

  // Static TX buffer (hdr + payload + crc)
  static uint8_t tx[sizeof(hdr) + FRAME_SAMPLES * 2 + 2];

  const size_t payload_bytes = (size_t)nsamp * 2;
  memcpy(tx, hdr, sizeof(hdr));
  memcpy(tx + sizeof(hdr), samples, payload_bytes);

  uint16_t crc = crc16_ccitt(tx, sizeof(hdr) + payload_bytes);
  tx[sizeof(hdr) + payload_bytes + 0] = (uint8_t)(crc & 0xFF);
  tx[sizeof(hdr) + payload_bytes + 1] = (uint8_t)(crc >> 8);

  // NOTE: This may still block, but now it's outside the sampling scheduler.
  Serial1.write(tx, sizeof(hdr) + payload_bytes + 2);
}

static inline void sample_into_buffers() {
  int v = analogRead(ANALOG_PIN);

  if (useA) bufA[idx] = (int16_t)v;
  else      bufB[idx] = (int16_t)v;

  idx++;
  if (idx >= FRAME_SAMPLES) {
    if (useA) bufA_ready = true;
    else      bufB_ready = true;

    useA = !useA;
    idx = 0;
  }
}

void setup() {
  analogReadResolution(12);
  Serial1.begin(BAUD);
  delay(100);
}

void loop() {
  static uint32_t next_t = micros();

  // 1) Maintain sampling schedule
  uint32_t now = micros();
  while (time_reached(now, next_t)) {
    sample_into_buffers();
    next_t += PERIOD_US;
    rem_accum += REM_US_NUM;
    if (rem_accum >= SAMPLE_RATE_HZ) {
      next_t += 1;
      rem_accum -= SAMPLE_RATE_HZ;
    }
    now = micros();
  }

  // 2) Transmit any ready frame(s) in "idle" time
  if (bufA_ready) {
    bufA_ready = false;
    build_and_send_frame(bufA, FRAME_SAMPLES, seq++);
  }
  if (bufB_ready) {
    bufB_ready = false;
    build_and_send_frame(bufB, FRAME_SAMPLES, seq++);
  }
}
