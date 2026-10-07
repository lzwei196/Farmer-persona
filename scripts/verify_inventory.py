#!/usr/bin/env python3
"""Check the saved Paper 1 response-grid inventory without printing profile IDs."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "raw_agent_output"
PROVIDERS = ("claude", "codex", "kimi")
TIERS = (1, 2, 3, 4)
EXPECTED_PER_CELL = {"quzhou": 505, "lsms": 280}


def inspect_cell(folder: Path) -> tuple[int, int, set[str]]:
    paths = sorted(folder.glob("*.json"))
    parsed = 0
    for path in paths:
        with path.open(encoding="utf-8") as handle:
            record = json.load(handle)
        if record.get("decision") is not None:
            parsed += 1
    return len(paths), parsed, {path.name for path in paths}


def main() -> int:
    failures: list[str] = []
    primary_count = primary_parsed = 0
    print("dataset,provider,tier,stored,parsed")

    for dataset, expected in EXPECTED_PER_CELL.items():
        reference_names: set[str] | None = None
        for provider in PROVIDERS:
            for tier in TIERS:
                folder = RAW / dataset / provider / f"tier{tier}"
                count, parsed, names = inspect_cell(folder)
                print(f"{dataset},{provider},T{tier},{count},{parsed}")
                primary_count += count
                primary_parsed += parsed
                if count != expected:
                    failures.append(f"{dataset}/{provider}/T{tier}: expected {expected}, got {count}")
                if reference_names is None:
                    reference_names = names
                elif names != reference_names:
                    failures.append(f"{dataset}/{provider}/T{tier}: profile filename set differs")

    auxiliary = sum(
        (RAW / dataset / filename).is_file()
        for dataset in EXPECTED_PER_CELL
        for filename in ("_metadata.json", "_ground_truth.json")
    )
    all_json = sum(1 for _ in RAW.rglob("*.json"))
    expected_total = primary_count + auxiliary
    if (primary_count, primary_parsed, auxiliary, all_json) != (9420, 9301, 4, 9424):
        failures.append(
            "unexpected totals: "
            f"primary={primary_count}, parsed={primary_parsed}, "
            f"auxiliary={auxiliary}, all_json={all_json}"
        )
    if all_json != expected_total:
        failures.append(f"unclassified JSON: {all_json - expected_total}")

    print(
        f"TOTAL primary={primary_count} parsed={primary_parsed} "
        f"auxiliary={auxiliary} all_json={all_json}"
    )
    for failure in failures:
        print(f"FAIL: {failure}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
