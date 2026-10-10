"""Strands UME -- persistent long-term memory for Strands agents, backed by UME.

:class:`UMEMemoryStore` is a Strands ``MemoryStore`` that plugs into the agent
loop via a :class:`~strands.memory.MemoryManager`, with automatic memory injection
and extraction. It implements both write sinks, so ``extraction`` uses UME's
server-side extraction (no extra model call).

For the explicit, model-called tool (``store`` / ``retrieve`` / ``get`` / ``delete``),
use the ``ume_memory`` tool from ``strands-agents-tools``; a store and the tool can
share one UME backend and namespace.
"""

from importlib.metadata import PackageNotFoundError, version

from ume_strands.client import UMEServiceClient
from ume_strands.store import UMEMemoryStore

__all__ = [
    "UMEMemoryStore",
    "UMEServiceClient",
]

try:
    __version__ = version("ume-strands")
except PackageNotFoundError:  # pragma: no cover - only when running from a source tree
    __version__ = "0.0.0+unknown"
