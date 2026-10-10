"""Regression tests pinning that the reranker fallback path never mutates caller-owned documents."""

from unittest.mock import MagicMock, patch

from ume.configs.rerankers.cohere import CohereRerankerConfig
from ume.configs.rerankers.huggingface import HuggingFaceRerankerConfig
from ume.configs.rerankers.sentence_transformer import (
    SentenceTransformerRerankerConfig,
)
from ume.configs.rerankers.zero_entropy import ZeroEntropyRerankerConfig
from ume.reranker.huggingface_reranker import HuggingFaceReranker
from ume.reranker.sentence_transformer_reranker import SentenceTransformerReranker


def _docs(n):
    return [{"memory": f"doc{i}"} for i in range(n)]


class TestCohereFallbackNoMutation:
    def test_fallback_does_not_mutate_original_documents(self, mock_cohere):
        module, fake_client = mock_cohere
        fake_client.rerank.side_effect = RuntimeError("API error")

        reranker = module.CohereReranker(CohereRerankerConfig(api_key="test-key"))
        documents = _docs(3)
        result = reranker.rerank("query", documents)

        assert all("rerank_score" not in doc for doc in documents)
        assert all(doc["rerank_score"] == 0.0 for doc in result)


class TestZeroEntropyFallbackNoMutation:
    def test_fallback_does_not_mutate_original_documents(self, mock_zero_entropy):
        module, fake_client = mock_zero_entropy
        fake_client.models.rerank.side_effect = RuntimeError("API error")

        reranker = module.ZeroEntropyReranker(ZeroEntropyRerankerConfig(api_key="test-key"))
        documents = _docs(3)
        result = reranker.rerank("query", documents)

        assert all("rerank_score" not in doc for doc in documents)
        assert all(doc["rerank_score"] == 0.0 for doc in result)


class TestHuggingFaceFallbackNoMutation:
    def test_fallback_does_not_mutate_original_documents(self):
        with (
            patch("ume.reranker.huggingface_reranker.AutoTokenizer") as mock_tokenizer_cls,
            patch("ume.reranker.huggingface_reranker.AutoModelForSequenceClassification") as mock_model_cls,
        ):
            mock_tokenizer = MagicMock(side_effect=RuntimeError("tokenizer error"))
            mock_tokenizer_cls.from_pretrained.return_value = mock_tokenizer
            mock_model_cls.from_pretrained.return_value = MagicMock()

            reranker = HuggingFaceReranker(HuggingFaceRerankerConfig())
            documents = _docs(3)
            result = reranker.rerank("query", documents)

        assert all("rerank_score" not in doc for doc in documents)
        assert all(doc["rerank_score"] == 0.0 for doc in result)


class TestSentenceTransformerFallbackNoMutation:
    def test_fallback_does_not_mutate_original_documents(self):
        with patch("ume.reranker.sentence_transformer_reranker.CrossEncoder") as mock_cross_encoder_cls:
            mock_model = MagicMock()
            mock_model.predict.side_effect = RuntimeError("predict error")
            mock_cross_encoder_cls.return_value = mock_model

            reranker = SentenceTransformerReranker(SentenceTransformerRerankerConfig())
            documents = _docs(3)
            result = reranker.rerank("query", documents)

        assert all("rerank_score" not in doc for doc in documents)
        assert all(doc["rerank_score"] == 0.0 for doc in result)
