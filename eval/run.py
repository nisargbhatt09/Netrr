#!/usr/bin/env python
"""Evaluation harness skeleton for Netrr.

Run any narrator backend over a fixed frame set and dump claim-level output as
JSONL, with no camera, speaker, or microphone. This is the reproducibility entry
point from plan v2 (section 5): one command -> one JSONL of claims.

Usage:
    python eval/run.py --frames frames --backend detector --out results/claims.jsonl

The I/O contract is real and tested end to end on the seeded fixture set; the
perception backends that emit `Claim` objects are the next increment.
"""

from __future__ import annotations

import argparse
import json
import os


def iter_frames(frames_dir):
    """Yield image paths in a stable order."""
    for name in sorted(os.listdir(frames_dir)):
        if name.lower().endswith((".png", ".jpg", ".jpeg")):
            yield os.path.join(frames_dir, name)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Netrr evaluation harness")
    parser.add_argument("--frames", default="frames", help="directory of frames")
    parser.add_argument("--out", default="results/claims.jsonl", help="output JSONL")
    parser.add_argument(
        "--backend",
        default="detector",
        choices=["detector", "local_vlm", "cloud_vlm"],
        help="narrator backend",
    )
    args = parser.parse_args(argv)

    frames = list(iter_frames(args.frames))
    out_dir = os.path.dirname(args.out)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    # Placeholder: a real backend emits Claim objects; the harness serialises
    # them. This proves the I/O contract on the fixture set.
    with open(args.out, "w") as fh:
        for frame in frames:
            record = {"frame": frame, "backend": args.backend, "claims": []}
            fh.write(json.dumps(record) + "\n")

    print(f"wrote {len(frames)} frame records to {args.out} (backend={args.backend})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
