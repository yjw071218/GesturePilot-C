from __future__ import annotations

import argparse
import json
import random
import shutil
from dataclasses import dataclass
from pathlib import Path


CLASS_MAP = {
    "0": "fist",
    "1": "point",
    "2": "v_sign",
    "3": "three",
    "4": "four",
    "5": "open_palm",
}


@dataclass
class SplitStats:
    train: int = 0
    val: int = 0


def reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def collect_images(source_root: Path, digit: str) -> list[Path]:
    class_dir = source_root / digit
    return sorted([p for p in class_dir.glob("*") if p.is_file()])


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare GesturePilot training dataset from Sign Language Digits.")
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("data/raw/sign-language-digits/Dataset"),
        help="Raw dataset folder containing digit class directories.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/gesture_dataset"),
        help="Output dataset root.",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--val-ratio", type=float, default=0.2, help="Validation split ratio")
    args = parser.parse_args()

    source = args.source.resolve()
    output = args.output.resolve()
    train_root = output / "train"
    val_root = output / "val"

    random.seed(args.seed)
    reset_dir(train_root)
    reset_dir(val_root)

    summary: dict[str, SplitStats] = {}
    total_train = 0
    total_val = 0

    for digit, class_name in CLASS_MAP.items():
        images = collect_images(source, digit)
        if not images:
            raise FileNotFoundError(f"No images found for digit class '{digit}' in {source}")

        random.shuffle(images)
        val_count = max(1, int(len(images) * args.val_ratio))
        val_images = images[:val_count]
        train_images = images[val_count:]

        train_class_dir = train_root / class_name
        val_class_dir = val_root / class_name
        train_class_dir.mkdir(parents=True, exist_ok=True)
        val_class_dir.mkdir(parents=True, exist_ok=True)

        for image_path in train_images:
            shutil.copy2(image_path, train_class_dir / image_path.name)
        for image_path in val_images:
            shutil.copy2(image_path, val_class_dir / image_path.name)

        summary[class_name] = SplitStats(train=len(train_images), val=len(val_images))
        total_train += len(train_images)
        total_val += len(val_images)

    metadata = {
        "source_dataset": str(source),
        "output_dataset": str(output),
        "classes": list(CLASS_MAP.values()),
        "class_map": CLASS_MAP,
        "seed": args.seed,
        "val_ratio": args.val_ratio,
        "totals": {"train": total_train, "val": total_val, "all": total_train + total_val},
        "per_class": {k: {"train": v.train, "val": v.val} for k, v in summary.items()},
    }

    output.mkdir(parents=True, exist_ok=True)
    (output / "dataset_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()

