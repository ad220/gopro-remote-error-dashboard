#!/usr/bin/env python3
"""
Seed script — creates API keys for v4.0/v4.1/v4.2 and sends 200 realistic
error reports so the admin UI has something meaningful to display.

Usage:
    python seed_reports.py [--url http://localhost:8000]

No third-party dependencies required (stdlib only).
"""

import argparse
import json
import random
import time
import urllib.request
import urllib.error
from collections import defaultdict

# ---------------------------------------------------------------------------
# Error code construction — mirrors ErrorManager.mc bit layout
# ---------------------------------------------------------------------------

_BUILD_FLAGS = {"ble": 0b00, "mobile_highend": 0b01, "mobile_lowend": 0b11}


def make_code(build: str, gopro_id: int, ec: int, data: int) -> int:
    return (_BUILD_FLAGS[build] << 30) | (gopro_id << 24) | (ec << 16) | (data & 0xFFFF)


# ---------------------------------------------------------------------------
# Realistic sampling
# ---------------------------------------------------------------------------

def _build() -> str:
    return random.choices(
        ["ble",  "mobile_highend", "mobile_lowend"],
        weights=[82,  13,              5],
    )[0]


def _gopro_id(version: str) -> int:
    if version == "v4.0":
        ids, w = [16, 15, 14, 17, 13, 19], [45, 20, 15, 10,  7,  3]
    elif version == "v4.1":
        ids, w = [16, 17, 15, 19, 14, 13], [35, 25, 15, 13,  8,  4]
    else:
        ids, w = [17, 19, 16, 15, 14, 13], [30, 28, 22, 12,  5,  3]
    return random.choices(ids, weights=w)[0]


def _error_code(build: str, gopro_id: int, version: str) -> int:
    if version == "v4.0":
        cats, w = ["ERR_COMM", "ERR_CAM", "ERR_NULL", "ERR_SYS", "ERR_MSG"], [42, 27, 20,  7, 4]
    elif version == "v4.1":
        cats, w = ["ERR_COMM", "ERR_CAM", "ERR_NULL", "ERR_SYS", "ERR_MSG"], [45, 30, 14,  6, 5]
    else:
        cats, w = ["ERR_COMM", "ERR_CAM", "ERR_NULL", "ERR_SYS", "ERR_MSG"], [48, 33, 10,  5, 4]

    cat = random.choices(cats, weights=w)[0]

    if cat == "ERR_COMM":
        # EC byte is always 0x20; SUB_BLE_* lives in the upper nibble of data0.
        # Extra context goes in the lower nibble of data0, data1 is rarely used.
        ec = 0x20
        sub = random.choices(
            [0x00, 0x10, 0x40, 0x80, 0x90, 0xA0, 0xF0],
            weights=[28,  8,   15,   5,   12,  20,  12],
        )[0]
        ctx  = random.choices([0, 1, 2, 3, 5, 0xF], weights=[30, 20, 20, 15, 10, 5])[0]
        data = sub | ctx   # data0 = SUB_BLE_* | context nibble

    elif cat == "ERR_CAM":
        # EC byte = ERR_CAM(0x80) | SUB_CAM_*(bits 5-4) | extra_context(bits 3-0)
        sub = random.choices(
            [0x00, 0x10, 0x20, 0x30],
            weights=[20,  38,  27,  15],
        )[0]
        ctx = random.choices([0, 1, 2, 3, 7, 8], weights=[55, 15, 12, 10, 5, 3])[0]
        ec   = 0x80 | sub | ctx
        setting_ids = [2, 3, 83, 91, 121, 134, 135]
        val  = random.randint(0, 255)
        data = (val << 8) | random.choice(setting_ids)

    elif cat == "ERR_MSG":
        # EC byte = ERR_MSG(0x40) | SUB_MSG_*(bits 5-4) | extra_context(bits 3-0)
        sub = random.choices([0x00, 0x10, 0x20], weights=[50, 30, 20])[0]
        ctx = random.choices([0, 1, 2, 3], weights=[65, 20, 10, 5])[0]
        ec   = 0x40 | sub | ctx
        data = random.choice([0x0000, 0x0001, 0x0002, 0x0003])

    elif cat == "ERR_NULL":
        ec   = 0x00
        data = random.choices(
            [0x0003, 0x0007, 0x0008, 0x000A, 0x000E, 0x0001, 0x0002],
            weights=[28,    22,     18,     14,     9,     5,     4],
        )[0]

    else:  # ERR_SYS
        ec   = 0x10
        data = random.choice([0x002A, 0x0067, 0x001F, 0x0042, 0x00DC])

    return make_code(build, gopro_id, ec, data)


# ---------------------------------------------------------------------------
# HTTP helpers (stdlib only)
# ---------------------------------------------------------------------------

BASE = "http://localhost:8000"


def _post(path: str, body=None, headers: dict | None = None):
    url     = BASE + path
    payload = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    with urllib.request.urlopen(req) as r:
        return None if r.status == 204 else json.loads(r.read())


def _get(path: str) -> dict:
    with urllib.request.urlopen(BASE + path) as r:
        return json.loads(r.read())


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url",  default="http://localhost:8000")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    global BASE
    BASE = args.url.rstrip("/")
    random.seed(args.seed)

    print(f"Target : {BASE}")
    print(f"Seed   : {args.seed}\n")

    # --- Create one API key per version ---
    version_counts = {"v4.0": 70, "v4.1": 90, "v4.2": 40}
    version_keys: dict[str, str] = {}

    print("Creating API keys...")
    for version in version_counts:
        try:
            result = _post("/admin/versions", {"version": version})
            version_keys[version] = result["key"]
            print(f"  {version}  {result['key'][:20]}...")
        except urllib.error.URLError as e:
            print(f"\nCould not reach {BASE}: {e}")
            print("Is the backend running?  uvicorn main:app --reload")
            return 1

    # --- Generate and send errors in realistic session batches ---
    print(f"\nSending {sum(version_counts.values())} errors...")

    for version, count in version_counts.items():
        codes = [
            _error_code(_build(), _gopro_id(version), version)
            for _ in range(count)
        ]

        key, sessions, i = version_keys[version], 0, 0
        while i < len(codes):
            # Most sessions flush a short queue; occasionally a longer one
            size  = random.choices([1, 2, 3, 4, 5, 8, 10], weights=[15, 25, 25, 18, 10, 5, 2])[0]
            batch = codes[i:i + size]
            _post("/report", {"errors": batch}, {"X-API-Key": key})
            sessions += 1
            i += size
            time.sleep(0.01)

        print(f"  {version}  {count:3d} errors  {sessions:2d} sessions")

    # --- Server-side confirmation ---
    stats = _get("/admin/stats")
    print(f"\nStored : {stats['total_reports']} reports")
    print(f"By version    : {stats['by_version']}")
    print(f"By category   : {stats['by_error_category']}")
    print(f"By camera     : {stats['by_gopro_model']}")
    print(f"By build      : {stats['by_build_flags']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
