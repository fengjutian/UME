import importlib.metadata

__version__ = importlib.metadata.version("ume")

from ume.client.main import AsyncMemoryClient, MemoryClient  # noqa
from ume.memory.main import AsyncMemory, Memory  # noqa
