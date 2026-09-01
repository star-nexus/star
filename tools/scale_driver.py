#!/usr/bin/env python3
"""Control STAR's local Scale Test Harness over a Unix Domain Socket."""

from __future__ import annotations

import argparse
import json
import socket
import sys
from typing import Any, Dict


def request(socket_path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        client.connect(socket_path)
        client.sendall((json.dumps(payload, separators=(",", ":")) + "\n").encode())
        chunks = bytearray()
        while b"\n" not in chunks:
            chunk = client.recv(65536)
            if not chunk:
                raise RuntimeError("scale harness closed the socket before replying")
            chunks.extend(chunk)
        line = bytes(chunks).split(b"\n", 1)[0]
        return json.loads(line.decode("utf-8"))
    finally:
        client.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="STAR Scale Test Harness control client"
    )
    parser.add_argument(
        "--socket",
        default="/tmp/star-scale.sock",
        help="Unix socket path (default: /tmp/star-scale.sock)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    prepare = sub.add_parser(
        "prepare", help="Generate random targets and batch-plan/correct moves"
    )
    prepare.add_argument("--density", type=float, default=1.0)
    prepare.add_argument("--seed", type=int, default=42)
    prepare.add_argument("--target-radius", type=int, default=12)
    prepare.add_argument(
        "--policy",
        choices=["normal", "stress_stack_endpoint"],
        default="stress_stack_endpoint",
    )

    start = sub.add_parser(
        "start", help="Execute the prepared MovePlans without pathfinding"
    )
    start.add_argument("--batch-id", type=int, default=None)

    sub.add_parser("status", help="Show prepared batch and current moving density")
    sub.add_parser("clear", help="Discard the prepared batch")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "prepare":
        payload = {
            "command": "prepare_random_moves",
            "density": args.density,
            "seed": args.seed,
            "target_radius": args.target_radius,
            "policy": args.policy,
        }
    elif args.command == "start":
        payload = {"command": "start_prepared_batch"}
        if args.batch_id is not None:
            payload["batch_id"] = args.batch_id
    else:
        payload = {"command": args.command}

    response = request(args.socket, payload)
    print(json.dumps(response, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if response.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
