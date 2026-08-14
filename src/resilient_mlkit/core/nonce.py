"""Run nonces.

Every ``mlkit`` invocation mints a nonce and prints it. The nonce exists so
that a pasted transcript can be told apart from a remembered or re-typed one:
a stdout block quoting a nonce that no run produced is a forgery, and a block
quoting a nonce from an earlier run is stale evidence being passed off as
current.
"""

from __future__ import annotations

import datetime as _dt
import os
import secrets


def mint() -> str:
    """Return a fresh run nonce.

    Format is ``mlkit-<utc-compact>-<random>``. The timestamp half makes
    ordering obvious to a human reader; the random half is what makes the
    nonce unforgeable by anything that isn't this process.
    """
    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"mlkit-{stamp}-{secrets.token_hex(6)}"


def from_env_or_mint() -> str:
    """Honour an externally supplied nonce, else mint one.

    CI sets ``MLKIT_RUN_NONCE`` so that several ``mlkit`` calls inside one
    workflow share a nonce and can be correlated. Interactive runs mint per
    invocation.
    """
    supplied = os.environ.get("MLKIT_RUN_NONCE", "").strip()
    return supplied or mint()
