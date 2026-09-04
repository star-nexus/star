"""Declarative regression gate for STAR profiler JSON snapshots.

The gate deliberately knows nothing about a particular machine or workload.
Contracts decide which metrics are portable structural/causal invariants and
which timing thresholds are valid only on a pinned benchmark host.

Example:

    uv run python tools/performance_gate.py \
      --profile /tmp/profile.json \
      --contract tools/performance_contract_static_window.yaml
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


SUPPORTED_OPS = {
    "exists",
    "eq",
    "ne",
    "lt",
    "lte",
    "gt",
    "gte",
    "contains",
    "not_contains",
}


class ContractError(ValueError):
    """Raised when a performance contract is malformed."""


@dataclass(frozen=True)
class RuleResult:
    path: str
    op: str
    expected: Any
    actual: Any
    passed: bool
    description: str = ""


def resolve_path(document: Any, path: str) -> tuple[bool, Any]:
    """Resolve a dotted path through dictionaries and integer list indices."""
    if not path:
        return True, document
    current = document
    for token in path.split("."):
        if isinstance(current, dict):
            if token not in current:
                return False, None
            current = current[token]
            continue
        if isinstance(current, list):
            try:
                index = int(token)
            except ValueError:
                return False, None
            if index < 0 or index >= len(current):
                return False, None
            current = current[index]
            continue
        return False, None
    return True, current


def _compare(*, exists: bool, actual: Any, op: str, expected: Any) -> bool:
    if op == "exists":
        return exists is bool(expected)
    if not exists:
        return False
    if op == "eq":
        return actual == expected
    if op == "ne":
        return actual != expected
    if op == "lt":
        return actual < expected
    if op == "lte":
        return actual <= expected
    if op == "gt":
        return actual > expected
    if op == "gte":
        return actual >= expected
    if op == "contains":
        return expected in actual
    if op == "not_contains":
        return expected not in actual
    raise ContractError(f"unsupported operator: {op}")


def evaluate_contract(profile: dict[str, Any], contract: dict[str, Any]) -> list[RuleResult]:
    """Evaluate all rules; malformed contracts raise ContractError."""
    rules = contract.get("rules")
    if not isinstance(rules, list) or not rules:
        raise ContractError("contract must contain a non-empty 'rules' list")

    results: list[RuleResult] = []
    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            raise ContractError(f"rule {index} must be a mapping")
        path = rule.get("path")
        op = rule.get("op")
        if not isinstance(path, str) or not path:
            raise ContractError(f"rule {index} requires a non-empty string 'path'")
        if op not in SUPPORTED_OPS:
            raise ContractError(f"rule {index} has unsupported op {op!r}")
        if "value" not in rule:
            raise ContractError(f"rule {index} requires 'value'")

        expected = rule["value"]
        exists, actual = resolve_path(profile, path)
        try:
            passed = _compare(exists=exists, actual=actual, op=op, expected=expected)
        except (TypeError, ValueError) as exc:
            raise ContractError(
                f"rule {index} cannot compare {path!r}: {actual!r} {op} {expected!r}"
            ) from exc
        results.append(
            RuleResult(
                path=path,
                op=op,
                expected=expected,
                actual=actual if exists else "<missing>",
                passed=passed,
                description=str(rule.get("description", "")),
            )
        )
    return results


def load_mapping(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.exists():
        raise ContractError(f"file not found: {source}")
    try:
        if source.suffix.lower() == ".json":
            data = json.loads(source.read_text(encoding="utf-8"))
        else:
            data = yaml.safe_load(source.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ContractError(f"failed to parse {source}: {exc}") from exc
    if not isinstance(data, dict):
        raise ContractError(f"{source} must contain a mapping/object")
    return data


def _format_result(result: RuleResult) -> str:
    mark = "PASS" if result.passed else "FAIL"
    detail = (
        f"{result.path} {result.op} {result.expected!r}; actual={result.actual!r}"
    )
    if result.description:
        detail += f" — {result.description}"
    return f"[{mark}] {detail}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate STAR performance regression rules")
    parser.add_argument("--profile", required=True, help="Profiler JSON snapshot")
    parser.add_argument("--contract", required=True, help="YAML/JSON performance contract")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        profile = load_mapping(args.profile)
        contract = load_mapping(args.contract)
        results = evaluate_contract(profile, contract)
    except ContractError as exc:
        print(f"performance gate error: {exc}")
        return 2

    name = contract.get("name", Path(args.contract).name)
    print(f"STAR performance gate: {name}")
    for result in results:
        print(_format_result(result))
    failures = sum(not result.passed for result in results)
    print(f"result: {'PASS' if failures == 0 else 'FAIL'} ({len(results) - failures}/{len(results)} rules)")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
