#!/usr/bin/env python3
"""Prepare an embedded image-to-editable-ppt run from codex-ppt slide images.

This script is intentionally a bridge, not a page reconstructor. It collects the
final origin_image/slide_XX.png files, calls the embedded editppt prepare
command, then reports the prepared run and the next required state-machine step.
Page reconstruction is still owned by the embedded editable module.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


SLIDE_RE = re.compile(r"^slide_(\d+)\.(png|jpg|jpeg|webp)$", re.IGNORECASE)


def die(message: str, code: int = 1) -> None:
    print(f"Error: {message}", file=sys.stderr)
    raise SystemExit(code)


def skill_root() -> Path:
    return Path(__file__).resolve().parents[1]


def embedded_editppt_cli() -> Path:
    cli = skill_root() / "editable" / "cli" / "editppt" / "cli.py"
    if not cli.exists():
        die(f"embedded editppt CLI not found: {cli}")
    return cli


def slide_sort_key(path: Path) -> tuple[int, str]:
    match = SLIDE_RE.match(path.name)
    if not match:
        return (10**9, path.name)
    return (int(match.group(1)), path.name)


def collect_slide_images(image_dir: Path) -> list[Path]:
    if not image_dir.exists():
        die(f"slide image directory not found: {image_dir}")
    images = sorted(
        [path for path in image_dir.iterdir() if path.is_file() and SLIDE_RE.match(path.name)],
        key=slide_sort_key,
    )
    if not images:
        die(f"no final slide images found in {image_dir}; expected slide_XX.png")
    return images


def run_command(argv: list[str], *, dry_run: bool) -> subprocess.CompletedProcess[str] | None:
    if dry_run:
        print(json.dumps({"dry_run_command": argv}, ensure_ascii=False))
        return None
    return subprocess.run(argv, text=True, capture_output=True)


def extract_deck_manifest(stdout: str) -> Path | None:
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    for line in reversed(lines):
        candidate = Path(line)
        if candidate.name == "deck_manifest.json":
            return candidate
    return None


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare editable reconstruction from a codex-ppt project directory."
    )
    parser.add_argument(
        "project_dir",
        help="Deck project directory containing origin_image/slide_XX.png files.",
    )
    parser.add_argument(
        "--image-dir",
        help="Override slide image directory. Defaults to PROJECT_DIR/origin_image.",
    )
    parser.add_argument(
        "--job-dir",
        help="Editable run directory. Defaults to PROJECT_DIR/editable_run.",
    )
    parser.add_argument(
        "--max-concurrent-pages",
        type=int,
        default=6,
        help="Maximum editable page-worker slots passed to editppt prepare.",
    )
    parser.add_argument(
        "--no-text-hints",
        action="store_true",
        help="Skip text hint generation during prepare.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands without running them.",
    )
    args = parser.parse_args()

    project_dir = Path(args.project_dir).expanduser().resolve()
    image_dir = Path(args.image_dir).expanduser().resolve() if args.image_dir else project_dir / "origin_image"
    job_dir = Path(args.job_dir).expanduser().resolve() if args.job_dir else project_dir / "editable_run"

    images = collect_slide_images(image_dir)
    cli = embedded_editppt_cli()

    prepare_cmd = [
        sys.executable,
        str(cli),
        "prepare",
        *[str(path) for path in images],
        "--job-dir",
        str(job_dir),
        "--max-concurrent-pages",
        str(args.max_concurrent_pages),
    ]
    if args.no_text_hints:
        prepare_cmd.append("--no-text-hints")

    prepared = run_command(prepare_cmd, dry_run=args.dry_run)
    if prepared is None:
        print(
            json.dumps(
                {
                    "project_dir": str(project_dir),
                    "image_dir": str(image_dir),
                    "image_count": len(images),
                    "job_dir": str(job_dir),
                    "next_command": [
                        sys.executable,
                        str(cli),
                        "run",
                        "next",
                        str(job_dir),
                        "--json",
                    ],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    if prepared.stdout:
        print(prepared.stdout, end="")
    if prepared.stderr:
        print(prepared.stderr, end="", file=sys.stderr)
    if prepared.returncode != 0:
        return prepared.returncode

    deck_manifest = extract_deck_manifest(prepared.stdout) or job_dir / "deck_manifest.json"
    if not deck_manifest.exists():
        die(f"prepare succeeded but deck_manifest.json was not found: {deck_manifest}")

    next_cmd = [sys.executable, str(cli), "run", "next", str(job_dir), "--json"]
    next_step = run_command(next_cmd, dry_run=False)
    next_payload: Any = None
    if next_step and next_step.returncode == 0 and next_step.stdout.strip():
        try:
            next_payload = json.loads(next_step.stdout)
        except json.JSONDecodeError:
            next_payload = next_step.stdout.strip()

    deck = load_json(deck_manifest)
    summary = {
        "project_dir": str(project_dir),
        "image_dir": str(image_dir),
        "image_count": len(images),
        "run_dir": str(job_dir),
        "deck_manifest": str(deck_manifest),
        "output": str((job_dir / deck.get("output", "final/deck_edited.pptx")).resolve()),
        "next": next_payload,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
