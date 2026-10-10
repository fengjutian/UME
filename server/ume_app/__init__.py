"""UME business layer.

Sits on top of the self-hosted server package (`server/`) and the memory engine
SDK (`ume/`). `server/` itself is the import root inside the container, so
submodules import each other as `ume_app.*` — that also keeps this package
distinct from the top-level SDK package of the same short name.
"""

__all__ = ["__version__"]

__version__ = "1.0.0"
