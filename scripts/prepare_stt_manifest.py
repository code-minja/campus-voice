#!/usr/bin/env python3
"""Create a CSV manifest from the local STT recording folders.

The current training recordings use the spoken sentence as the filename, so this
script turns filenames such as:

    stt-training-data/STT Noisy/take me to agric lt.m4a

into rows like:

    audio_path,transcript,split,condition
    stt-training-data/STT Noisy/take me to agric lt.m4a,take me to agric lt,train,noisy

Use this manifest for baseline evaluation, dataset review, and later Whisper
fine-tuning with Hugging Face Datasets.
"""

from __future__ import annotations

import argparse
import csv
import random
import re
from pathlib import Path


AUDIO_EXTENSIONS = {".m4a", ".mp3", ".wav", ".flac", ".ogg", ".webm"}


def transcript_from_filename(path: Path) -> str:
    """Infer the intended transcript from a recording filename."""
    text = path.stem
    text = re.sub(r"\bNS\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def condition_from_path(path: Path) -> str:
    folder = path.parent.name.lower()
    if "noisy" in folder:
        return "noisy"
    if "ns" in folder:
        return "noise_suppressed"
    return "unknown"


def build_rows(data_dir: Path, test_ratio: float, seed: int) -> list[dict[str, str]]:
    audio_files = sorted(
        path
        for path in data_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS
    )
    if not audio_files:
        raise SystemExit(f"No audio files found under {data_dir}")

    rng = random.Random(seed)
    rng.shuffle(audio_files)

    test_count = max(1, round(len(audio_files) * test_ratio))
    test_files = set(audio_files[:test_count])

    rows: list[dict[str, str]] = []
    for path in sorted(audio_files):
        rows.append(
            {
                "audio_path": path.as_posix(),
                "transcript": transcript_from_filename(path),
                "split": "test" if path in test_files else "train",
                "condition": condition_from_path(path),
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("stt-training-data"),
        help="Directory containing STT recording folders.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("stt-training-data/metadata.csv"),
        help="CSV manifest to write.",
    )
    parser.add_argument(
        "--test-ratio",
        type=float,
        default=0.2,
        help="Fraction of files to reserve for evaluation.",
    )
    parser.add_argument("--seed", type=int, default=7, help="Train/test split seed.")
    args = parser.parse_args()

    rows = build_rows(args.data_dir, args.test_ratio, args.seed)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["audio_path", "transcript", "split", "condition"]
        )
        writer.writeheader()
        writer.writerows(rows)

    train_count = sum(row["split"] == "train" for row in rows)
    test_count = sum(row["split"] == "test" for row in rows)
    print(f"Wrote {args.output} with {train_count} train and {test_count} test rows.")


if __name__ == "__main__":
    main()
