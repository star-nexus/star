"""
Reproducibility-focused RNG service.

`RngService` is a singleton ECS component that owns one deterministic
`random.Random` instance per named domain (e.g. "combat", "events",
"render", "map"). Each domain handle is seeded by a stable hash of the
root seed plus the domain name, so:

- Reproducibility: a fixed root seed makes every domain reproducible.
- Decoupling: reordering or adding draws in one domain does not perturb
  another. Adding new domains never changes existing trajectories.
- Inspection: the root seed is persisted in `GameStats.map_info["game_seed"]`
  so settlement reports / leaderboard tooling can correlate seed → outcome.

If callers cannot reach the world (e.g. dataclass methods on components),
they may accept an explicit `rng: random.Random` parameter and fall back
to the module-level `random` when `rng is None` (preserves prior, non-
deterministic behavior).
"""

from __future__ import annotations

import hashlib
import os
import random
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

from framework import SingletonComponent


def _derive_domain_seed(root_seed: int, domain: str) -> int:
    """Derive a stable 64-bit seed for `domain` from `root_seed`."""
    payload = f"{int(root_seed)}:{domain}".encode()
    digest = hashlib.blake2b(payload, digest_size=8).digest()
    return int.from_bytes(digest, "big", signed=False)


def resolve_seed(cli_seed: Optional[int] = None, config_seed: Optional[int] = None) -> int:
    """Resolve the root seed using CLI > env `STAR_SEED` > config > wall-clock.

    Returning a concrete int (instead of `None`) lets the system always
    behave like a seeded run; when no seed is provided we fall back to a
    fresh wall-clock value, so default behavior keeps matches stochastic.
    """
    if cli_seed is not None:
        return int(cli_seed)
    env_seed = os.environ.get("STAR_SEED")
    if env_seed not in (None, ""):
        try:
            return int(env_seed)
        except ValueError:
            print(f"[RngService] ⚠️ STAR_SEED='{env_seed}' is not an integer; ignoring")
    if config_seed is not None:
        try:
            return int(config_seed)
        except (TypeError, ValueError):
            print(f"[RngService] ⚠️ config seed {config_seed!r} not an integer; ignoring")
    # Last-resort: wall-clock derived seed. Recorded so users can replay it.
    return int(time.time_ns() & 0xFFFFFFFF)


@dataclass
class RngService(SingletonComponent):
    """Deterministic per-domain RNG handles seeded from a single root."""

    seed: int = 0
    _rngs: Dict[str, random.Random] = field(default_factory=dict)
    # Optional provenance — useful in settlement reports / debugging
    source: str = "default"  # "cli" | "env" | "config" | "default"

    def get(self, domain: str) -> random.Random:
        """Return (and lazily create) a `random.Random` for `domain`."""
        rng = self._rngs.get(domain)
        if rng is None:
            rng = random.Random(_derive_domain_seed(self.seed, domain))
            self._rngs[domain] = rng
        return rng

    def snapshot(self) -> Dict[str, object]:
        """Return a JSON-serializable snapshot for inclusion in reports."""
        return {
            "seed": int(self.seed),
            "source": self.source,
            "domains": sorted(self._rngs.keys()),
        }
