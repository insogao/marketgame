from __future__ import annotations

import hashlib
import random


def derive_seed(master_seed: int, identity: str) -> int:
    digest = hashlib.blake2b(
        f"{master_seed}:{identity}".encode("utf-8"),
        digest_size=16,
    ).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


def make_deterministic_rng(master_seed: int, identity: str) -> random.Random:
    return random.Random(derive_seed(master_seed, identity))
