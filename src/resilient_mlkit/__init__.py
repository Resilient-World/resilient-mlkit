"""resilient-mlkit — the one measurement and gating tool for the portfolio.

Built once, imported everywhere. Never reimplemented per repo: eight
divergent copies of a gate is eight different definitions of "ready", which is
the same as having none.
"""

from .core.result import CheckResult, CredentialRequired, Status

#: The single declaration of this package's version.
#:
#: It was three declarations until E-M08: ``pyproject.toml``, this module and
#: ``cli.__version__`` each carried their own literal, and the ``v0.3.0`` tag
#: was cut with all three still reading ``0.2.0``. Three copies of a fact is
#: three chances for it to be wrong and no way to tell which one is. Here is
#: the copy: ``pyproject.toml`` reads it through ``[tool.setuptools.dynamic]``
#: and ``cli`` imports it, so a bump is one edit and a mismatch is
#: unconstructible rather than merely discouraged.
__version__ = "0.4.0"
__all__ = ["CheckResult", "CredentialRequired", "Status", "__version__"]
