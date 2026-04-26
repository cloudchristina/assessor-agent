"""CLI: python -m scripts.eval_run --suite=smoke|full --out=eval_run.json"""
from __future__ import annotations
import argparse
import json
import os
import subprocess
from pathlib import Path

from src.eval_harness.runner import run_eval_suite


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", choices=["smoke", "full"], default="smoke")
    ap.add_argument("--out", type=Path, default=Path("eval_run.json"))
    args = ap.parse_args()

    branch = os.environ.get("GITHUB_REF_NAME") or _git_branch()
    commit_sha = os.environ.get("GITHUB_SHA") or _git_sha()

    result = run_eval_suite(args.suite, branch=branch, commit_sha=commit_sha)
    args.out.write_text(json.dumps(result, indent=2, default=str))
    print(f"wrote {args.out}: {result['cases_run']} cases, suite={args.suite}")


def _git_branch() -> str:
    return subprocess.check_output(["git", "branch", "--show-current"], text=True).strip()


def _git_sha() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


if __name__ == "__main__":
    main()
