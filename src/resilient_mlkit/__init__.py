"""resilient-mlkit — the one measurement and gating tool for the portfolio.

Built once, imported everywhere. Never reimplemented per repo: eight
divergent copies of a gate is eight different definitions of "ready", which is
the same as having none.
"""

from .core.result import CheckResult, CredentialRequired, Status

__version__ = "0.2.0"
__all__ = ["CheckResult", "CredentialRequired", "Status", "__version__"]
