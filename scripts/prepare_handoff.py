#!/usr/bin/env python3
"""Offline preparation, preview approval and immutable delivery for the owner's A1 mini."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from plotnote.handoff import prepare, verify, approve, bundle
from plotnote.model import PlotNoteError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("prepare")
    p.add_argument("--request", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p = commands.add_parser("verify")
    p.add_argument("directory", type=Path)
    p = commands.add_parser("approve", help="Run only after a human explicitly approves this exact preview")
    p.add_argument("directory", type=Path)
    p.add_argument("--reviewer", required=True)
    p.add_argument("--preview-sha256", required=True)
    p = commands.add_parser("bundle")
    p.add_argument("directory", type=Path)
    p.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            result = prepare(args.request, args.output)
        elif args.command == "verify":
            result = verify(args.directory)
        elif args.command == "approve":
            result = approve(args.directory, args.reviewer, args.preview_sha256)
        else:
            result = bundle(args.directory, args.output)
        if args.command in ("prepare", "verify"):
            result = {"job_id": result["job_id"], "passes": len(result["passes"]), "preview_sha256": result["preview_sha256"], "approval": "not inferred; inspect approval.json separately"}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (PlotNoteError, OSError, ValueError) as error:
        parser.exit(2, f"Stopped: {error}\n")


if __name__ == "__main__":
    main()
