"""Regression test pinning the public exports of ``ume.reranker``.

All five rerankers are first-class providers in ``RerankerFactory``, so all five
classes must be importable from the package root. A regression once dropped the
LLM, HuggingFace, and ZeroEntropy rerankers from ``__init__`` while keeping them
in the factory, so ``from ume.reranker import LLMReranker`` raised ImportError.
"""

import ume.reranker as reranker_pkg


def test_all_rerankers_are_importable_from_package_root():
    from ume.reranker import (
        BaseReranker,
        CohereReranker,
        HuggingFaceReranker,
        LLMReranker,
        SentenceTransformerReranker,
        ZeroEntropyReranker,
    )

    assert {
        BaseReranker,
        CohereReranker,
        HuggingFaceReranker,
        LLMReranker,
        SentenceTransformerReranker,
        ZeroEntropyReranker,
    }


def test_all_exported_names_are_present_in_dunder_all():
    expected = {
        "BaseReranker",
        "CohereReranker",
        "HuggingFaceReranker",
        "LLMReranker",
        "SentenceTransformerReranker",
        "ZeroEntropyReranker",
    }
    assert expected <= set(reranker_pkg.__all__)
