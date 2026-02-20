#!/usr/bin/env python3
"""
UNO Q Linux: read ADC samples streamed from MCU over /dev/ttyHS1, run Edge Impulse .eim inference.

Usage:
  python3 unoq_adc_infer.py --model modelfile.eim --port /dev/ttyHS1 --baud 2000000 --frame-samples 512 --window-samples 11025

Notes:
- `window_samples` MUST match your model's expected raw sample count (e.g. 11025 for 250ms @ 44.1k).
- For audio-style models, you usually want centered samples (e.g., -1..1). Adjust normalization below.
"""

import argparse
import struct
import time
from collections import deque

import numpy as np
import serial
from edge_impulse_linux.runner import ImpulseRunner


MAGIC = 0xA55A

def crc16_ccitt(data: bytes, poly=0x1021, init=0xFFFF) -> int:
    crc = init
    for b in data:
        crc ^= (b << 8) & 0xFFFF
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ poly) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc & 0xFFFF


def read_exact(ser: serial.Serial, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = ser.read(n - len(buf))
        if not chunk:
            raise TimeoutError("Serial timeout while reading")
        buf.extend(chunk)
    return bytes(buf)


def find_magic(ser: serial.Serial) -> None:
    """Resync by scanning for MAGIC in the byte stream."""
    w = bytearray()
    while True:
        b = ser.read(1)
        if not b:
            raise TimeoutError("Serial timeout while searching for magic")
        w += b
        if len(w) > 2:
            w = w[-2:]
        if len(w) == 2:
            m = w[0] | (w[1] << 8)
            if m == MAGIC:
                return


def read_frame(ser: serial.Serial, expected_nsamp: int) -> tuple[int, np.ndarray]:
    """
    Read one frame and return (seq, samples int16 numpy array).
    """
    # Read seq (4) + nsamp (2)
    hdr_rest = read_exact(ser, 6)
    seq, nsamp = struct.unpack("<IH", hdr_rest)

    if nsamp <= 0 or nsamp > 4096:
        raise ValueError(f"nsamp out of range: {nsamp}")

    payload = read_exact(ser, nsamp * 2)
    crc_bytes = read_exact(ser, 2)
    (crc_rx,) = struct.unpack("<H", crc_bytes)

    # Recompute CRC over: MAGIC + seq+nsamp + payload
    hdr = struct.pack("<H", MAGIC) + hdr_rest
    crc_calc = crc16_ccitt(hdr + payload)

    if crc_calc != crc_rx:
        raise ValueError(f"CRC mismatch: calc={crc_calc:04x} rx={crc_rx:04x}")

    if expected_nsamp and nsamp != expected_nsamp:
        raise ValueError(f"Unexpected nsamp: got={nsamp} expected={expected_nsamp}")

    samples = np.frombuffer(payload, dtype="<i2")  # little-endian int16
    return seq, samples


def normalize_adc_to_float(samples_i16: np.ndarray, adc_bits: int = 12, center: bool = False) -> np.ndarray:
    """
    Convert raw ADC codes to float samples for EI.
    - If your ADC codes are 0..(2^bits-1), set center=False => 0..1
    - If you want a centered waveform (recommended for audio-like), set center=True => -1..1
    """
    max_code = float((1 << adc_bits) - 1)
    x = samples_i16.astype(np.float32)

    # Some cores return ADC code as int; we stored into int16, so values should be non-negative.
    x = np.clip(x, 0.0, max_code)

    if center:
        # map 0..max -> -1..1
        x = (x / max_code) * 2.0 - 1.0
    else:
        # map 0..max -> 0..1
        x = x / max_code

    return x


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="Path to .eim model file")
    ap.add_argument("--port", default="/dev/ttyHS1", help="Serial port (e.g. /dev/ttyHS1)")
    ap.add_argument("--baud", type=int, default=2000000, help="Serial baud rate")
    ap.add_argument("--frame-samples", type=int, default=512, help="Samples per MCU frame")
    ap.add_argument("--window-samples", type=int, default=11025, help="Samples per inference window")
    ap.add_argument("--adc-bits", type=int, default=12, help="ADC resolution used on MCU")
    ap.add_argument("--center", action="store_true", help="Center samples to -1..1")
    ap.add_argument("--timeout", type=float, default=1.0, help="Serial read timeout seconds")
    args = ap.parse_args()

    runner = ImpulseRunner(args.model)
    model_info = runner.init()

    print(f"Loaded model for: {model_info.get('project', {}).get('owner', '?')} / {model_info.get('project', {}).get('name', '?')}")
    print(f"Serial: {args.port} @ {args.baud}")
    print(f"Frame samples: {args.frame_samples} | Window samples: {args.window_samples}")

    ser = serial.Serial(args.port, baudrate=args.baud, timeout=args.timeout)

    ring = deque(maxlen=args.window_samples)
    last_seq = None
    last_print = time.time()

    try:
        while True:
            # Resync to frame boundary
            find_magic(ser)
            seq, s = read_frame(ser, expected_nsamp=args.frame_samples)

            if last_seq is not None and seq != (last_seq + 1):
                print(f"[warn] seq jump: {last_seq} -> {seq}")
            last_seq = seq

            xf = normalize_adc_to_float(s, adc_bits=args.adc_bits, center=args.center)
            ring.extend(xf.tolist())

            # When we have a full window, classify
            if len(ring) == args.window_samples:
                window = list(ring)
                res = runner.classify(window)

                now = time.time()
                if now - last_print > 0.2:
                    last_print = now
                    print("result:", res.get("result", {}))
                    print("timing:", res.get("timing", {}))
                    print("---")

    finally:
        ser.close()
        runner.stop()


if __name__ == "__main__":
    main()
