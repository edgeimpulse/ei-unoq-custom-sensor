#!/usr/bin/env python3
"""
UNO Q Linux: capture ADC frames from MCU over /dev/ttyHS1 and store to a file.

Outputs:
- out.raw : little-endian uint16 ADC codes (0..4095 for 12-bit), one per sample
- prints seq jump warnings + throughput stats

Usage:
  python3 linux/unoq_capture_to_file.py \
    --port /dev/ttyHS1 --baud 2000000 \
    --frame-samples 512 --adc-bits 12 \
    --seconds 30 --out out.raw
"""
from __future__ import annotations

import argparse
import struct
import time
from collections import deque
import serial

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

def read_frame(ser: serial.Serial, expected_nsamp: int) -> tuple[int, bytes]:
    # After MAGIC already consumed, read seq(4) + nsamp(2)
    hdr_rest = read_exact(ser, 6)
    seq, nsamp = struct.unpack("<IH", hdr_rest)
    if nsamp != expected_nsamp:
        # read payload anyway to resync safely
        payload = read_exact(ser, nsamp * 2)
        crc_bytes = read_exact(ser, 2)
        raise ValueError(f"nsamp mismatch: got {nsamp}, expected {expected_nsamp}")
    payload = read_exact(ser, nsamp * 2)
    crc_bytes = read_exact(ser, 2)
    (crc_rx,) = struct.unpack("<H", crc_bytes)

    # Reconstruct CRC input: MAGIC(2) + hdr_rest(6) + payload
    magic_bytes = struct.pack("<H", MAGIC)
    crc_calc = crc16_ccitt(magic_bytes + hdr_rest + payload)
    if crc_calc != crc_rx:
        raise ValueError(f"CRC mismatch: calc=0x{crc_calc:04X} rx=0x{crc_rx:04X}")
    return seq, payload

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/ttyHS1")
    ap.add_argument("--baud", type=int, default=2000000)
    ap.add_argument("--frame-samples", type=int, default=512)
    ap.add_argument("--adc-bits", type=int, default=12)
    ap.add_argument("--timeout", type=float, default=1.0)
    ap.add_argument("--seconds", type=float, default=10.0)
    ap.add_argument("--out", default="out.raw")
    args = ap.parse_args()

    ser = serial.Serial(args.port, baudrate=args.baud, timeout=args.timeout)

    total_samples = 0
    total_frames = 0
    last_seq = None
    seq_jumps = 0
    crc_errors = 0

    t0 = time.time()
    t_last = t0
    bytes_last = 0
    bytes_written = 0

    with open(args.out, "wb") as f:
        try:
            while True:
                now = time.time()
                if now - t0 >= args.seconds:
                    break

                try:
                    find_magic(ser)
                    seq, payload = read_frame(ser, expected_nsamp=args.frame_samples)
                except ValueError as e:
                    # CRC mismatch or nsamp mismatch
                    if "CRC mismatch" in str(e):
                        crc_errors += 1
                    continue

                if last_seq is not None and seq != (last_seq + 1):
                    seq_jumps += 1
                    print(f"[warn] seq jump: {last_seq} -> {seq}")
                last_seq = seq

                f.write(payload)  # raw uint16 ADC codes, little-endian
                bytes_written += len(payload)
                total_frames += 1
                total_samples += args.frame_samples

                # periodic stats
                if now - t_last >= 1.0:
                    dt = now - t_last
                    bps = (bytes_written - bytes_last) / dt
                    sps = (args.frame_samples * (total_frames)) / (now - t0)
                    print(f"[stats] {sps:.1f} samples/s, {bps/1024:.1f} KiB/s, frames={total_frames}, jumps={seq_jumps}, crc_err={crc_errors}")
                    t_last = now
                    bytes_last = bytes_written
        finally:
            ser.close()

    print("done")
    print(f"wrote: {args.out}")
    print(f"frames={total_frames}, samples={total_samples}, seq_jumps={seq_jumps}, crc_err={crc_errors}")

if __name__ == "__main__":
    main()