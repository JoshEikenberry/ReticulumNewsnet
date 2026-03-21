"""
Human-readable identity words derived deterministically from an RNS public key.

Algorithm (from spec):
    digest = SHA-256(public_key_bytes)   # 32 bytes
    n      = int.from_bytes(digest[:5], "big")  # 40-bit integer
    w3 = n % 7776;  n //= 7776
    w2 = n % 7776;  n //= 7776
    w1 = n % 7776
    display = wordlist[w1] + "·" + wordlist[w2] + "·" + wordlist[w3]

3 words from the EFF large wordlist (7776 entries) gives ~38.7 bits of entropy —
roughly 1-in-470-billion collision chance, sufficient for human disambiguation on
any realistically-sized network.
"""
from __future__ import annotations

import hashlib

from newsnet._wordlist import WORDLIST

_N = len(WORDLIST)  # 7776


def hash_to_words(public_key_bytes: bytes) -> str:
    """Return a deterministic 3-word phrase for the given RNS public key bytes."""
    digest = hashlib.sha256(public_key_bytes).digest()
    n = int.from_bytes(digest[:5], "big")
    w3 = n % _N;  n //= _N
    w2 = n % _N;  n //= _N
    w1 = n % _N
    return f"{WORDLIST[w1]}\u00b7{WORDLIST[w2]}\u00b7{WORDLIST[w3]}"
