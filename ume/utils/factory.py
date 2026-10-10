import importlib
import inspect
from typing import Dict, Optional, Union

from ume.configs.embeddings.base import BaseEmbedderConfig
from ume.configs.llms.anthropic import AnthropicConfig
from ume.configs.llms.aws_bedrock import AWSBedrockConfig
from ume.configs.llms.azure import AzureOpenAIConfig
from ume.configs.llms.base import BaseLlmConfig
from ume.configs.llms.deepseek import DeepSeekConfig
from ume.configs.llms.gemini import GeminiConfig
from ume.configs.llms.lmstudio import LMStudioConfig
from ume.configs.llms.minimax import MinimaxConfig
from ume.configs.llms.ollama import OllamaConfig
from ume.configs.llms.openai import OpenAIConfig
from ume.configs.llms.vllm import VllmConfig
from ume.configs.llms.xai import XAIConfig
from ume.configs.rerankers.base import BaseRerankerConfig
from ume.configs.rerankers.cohere import CohereRerankerConfig
from ume.configs.rerankers.huggingface import HuggingFaceRerankerConfig
from ume.configs.rerankers.llm import LLMRerankerConfig
from ume.configs.rerankers.sentence_transformer import (
    SentenceTransformerRerankerConfig,
)
from ume.configs.rerankers.zero_entropy import ZeroEntropyRerankerConfig
from ume.embeddings.mock import MockEmbeddings


def load_class(class_type):
    module_path, class_name = class_type.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


class LlmFactory:
    """
    Factory for creating LLM instances with appropriate configurations.
    Supports both old-style BaseLlmConfig and new provider-specific configs.
    """

    # Provider mappings with their config classes
    provider_to_class = {
        "ollama": ("ume.llms.ollama.OllamaLLM", OllamaConfig),
        "openai": ("ume.llms.openai.OpenAILLM", OpenAIConfig),
        "groq": ("ume.llms.groq.GroqLLM", BaseLlmConfig),
        "together": ("ume.llms.together.TogetherLLM", BaseLlmConfig),
        "aws_bedrock": ("ume.llms.aws_bedrock.AWSBedrockLLM", AWSBedrockConfig),
        "litellm": ("ume.llms.litellm.LiteLLM", BaseLlmConfig),
        "azure_openai": ("ume.llms.azure_openai.AzureOpenAILLM", AzureOpenAIConfig),
        "openai_structured": ("ume.llms.openai_structured.OpenAIStructuredLLM", OpenAIConfig),
        "anthropic": ("ume.llms.anthropic.AnthropicLLM", AnthropicConfig),
        "azure_openai_structured": ("ume.llms.azure_openai_structured.AzureOpenAIStructuredLLM", AzureOpenAIConfig),
        "gemini": ("ume.llms.gemini.GeminiLLM", GeminiConfig),
        "deepseek": ("ume.llms.deepseek.DeepSeekLLM", DeepSeekConfig),
        "minimax": ("ume.llms.minimax.MiniMaxLLM", MinimaxConfig),
        "xai": ("ume.llms.xai.XAILLM", XAIConfig),
        "sarvam": ("ume.llms.sarvam.SarvamLLM", BaseLlmConfig),
        "lmstudio": ("ume.llms.lmstudio.LMStudioLLM", LMStudioConfig),
        "vllm": ("ume.llms.vllm.VllmLLM", VllmConfig),
        "langchain": ("ume.llms.langchain.LangchainLLM", BaseLlmConfig),
    }

    @classmethod
    def create(cls, provider_name: str, config: Optional[Union[BaseLlmConfig, Dict]] = None, **kwargs):
        """
        Create an LLM instance with the appropriate configuration.

        Args:
            provider_name (str): The provider name (e.g., 'openai', 'anthropic')
            config: Configuration object or dict. If None, will create default config
            **kwargs: Additional configuration parameters

        Returns:
            Configured LLM instance

        Raises:
            ValueError: If provider is not supported
        """
        if provider_name not in cls.provider_to_class:
            raise ValueError(f"Unsupported Llm provider: {provider_name}")

        class_type, config_class = cls.provider_to_class[provider_name]
        llm_class = load_class(class_type)

        # Handle configuration
        if config is None:
            # Create default config with kwargs
            config = config_class(**kwargs)
        elif isinstance(config, dict):
            # Merge dict config with kwargs
            config = {**config, **kwargs}
            config = config_class(**config)
        elif isinstance(config, BaseLlmConfig):
            # Convert base config to provider-specific config if needed
            if config_class != BaseLlmConfig:
                # Convert to provider-specific config
                config_dict = {
                    "model": config.model,
                    "temperature": config.temperature,
                    "api_key": config.api_key,
                    "max_tokens": config.max_tokens,
                    "top_p": config.top_p,
                    "top_k": config.top_k,
                    "enable_vision": config.enable_vision,
                    "vision_details": config.vision_details,
                    "http_client_proxies": config.http_client_proxies,
                }
                # Only forward reasoning fields to provider configs that accept them
                # (explicitly or via **kwargs); others would raise on unexpected kwargs.
                params = inspect.signature(config_class).parameters
                accepts_kwargs = any(p.kind == p.VAR_KEYWORD for p in params.values())
                if accepts_kwargs or "reasoning_effort" in params:
                    config_dict["reasoning_effort"] = config.reasoning_effort
                if accepts_kwargs or "is_reasoning_model" in params:
                    config_dict["is_reasoning_model"] = config.is_reasoning_model
                config_dict.update(kwargs)
                config = config_class(**config_dict)
            else:
                # Use base config as-is
                pass
        else:
            # Assume it's already the correct config type
            pass

        return llm_class(config)

    @classmethod
    def register_provider(cls, name: str, class_path: str, config_class=None):
        """
        Register a new provider.

        Args:
            name (str): Provider name
            class_path (str): Full path to LLM class
            config_class: Configuration class for the provider (defaults to BaseLlmConfig)
        """
        if config_class is None:
            config_class = BaseLlmConfig
        cls.provider_to_class[name] = (class_path, config_class)

    @classmethod
    def get_supported_providers(cls) -> list:
        """
        Get list of supported providers.

        Returns:
            list: List of supported provider names
        """
        return list(cls.provider_to_class.keys())


class EmbedderFactory:
    provider_to_class = {
        "openai": "ume.embeddings.openai.OpenAIEmbedding",
        "ollama": "ume.embeddings.ollama.OllamaEmbedding",
        "huggingface": "ume.embeddings.huggingface.HuggingFaceEmbedding",
        "azure_openai": "ume.embeddings.azure_openai.AzureOpenAIEmbedding",
        "gemini": "ume.embeddings.gemini.GoogleGenAIEmbedding",
        "vertexai": "ume.embeddings.vertexai.VertexAIEmbedding",
        "together": "ume.embeddings.together.TogetherEmbedding",
        "lmstudio": "ume.embeddings.lmstudio.LMStudioEmbedding",
        "langchain": "ume.embeddings.langchain.LangchainEmbedding",
        "aws_bedrock": "ume.embeddings.aws_bedrock.AWSBedrockEmbedding",
        "fastembed": "ume.embeddings.fastembed.FastEmbedEmbedding",
    }

    @classmethod
    def create(cls, provider_name, config, vector_config: Optional[dict]):
        if provider_name == "upstash_vector" and vector_config and vector_config.enable_embeddings:
            return MockEmbeddings()
        class_type = cls.provider_to_class.get(provider_name)
        if class_type:
            embedder_instance = load_class(class_type)
            base_config = BaseEmbedderConfig(**config)
            return embedder_instance(base_config)
        else:
            raise ValueError(f"Unsupported Embedder provider: {provider_name}")


class VectorStoreFactory:
    provider_to_class = {
        "qdrant": "ume.vector_stores.qdrant.Qdrant",
        "chroma": "ume.vector_stores.chroma.ChromaDB",
        "pgvector": "ume.vector_stores.pgvector.PGVector",
        "milvus": "ume.vector_stores.milvus.MilvusDB",
        "upstash_vector": "ume.vector_stores.upstash_vector.UpstashVector",
        "azure_ai_search": "ume.vector_stores.azure_ai_search.AzureAISearch",
        "azure_mysql": "ume.vector_stores.azure_mysql.AzureMySQL",
        "pinecone": "ume.vector_stores.pinecone.PineconeDB",
        "mongodb": "ume.vector_stores.mongodb.MongoDB",
        "redis": "ume.vector_stores.redis.RedisDB",
        "valkey": "ume.vector_stores.valkey.ValkeyDB",
        "databricks": "ume.vector_stores.databricks.Databricks",
        "elasticsearch": "ume.vector_stores.elasticsearch.ElasticsearchDB",
        "vertex_ai_vector_search": "ume.vector_stores.vertex_ai_vector_search.GoogleMatchingEngine",
        "opensearch": "ume.vector_stores.opensearch.OpenSearchDB",
        "supabase": "ume.vector_stores.supabase.Supabase",
        "weaviate": "ume.vector_stores.weaviate.Weaviate",
        "faiss": "ume.vector_stores.faiss.FAISS",
        "langchain": "ume.vector_stores.langchain.Langchain",
        "s3_vectors": "ume.vector_stores.s3_vectors.S3Vectors",
        "baidu": "ume.vector_stores.baidu.BaiduDB",
        "cassandra": "ume.vector_stores.cassandra.CassandraDB",
        "neptune": "ume.vector_stores.neptune_analytics.NeptuneAnalyticsVector",
        "turbopuffer": "ume.vector_stores.turbopuffer.TurbopufferDB",
        "oracledb": "ume.vector_stores.oracledb.OracleAIVectorSearch",
    }

    @classmethod
    def create(cls, provider_name, config):
        class_type = cls.provider_to_class.get(provider_name)
        if class_type:
            if not isinstance(config, dict):
                config = config.model_dump()
            vector_store_instance = load_class(class_type)
            return vector_store_instance(**config)
        else:
            raise ValueError(f"Unsupported VectorStore provider: {provider_name}")

    @classmethod
    def reset(cls, instance):
        instance.reset()
        return instance


class RerankerFactory:
    """
    Factory for creating reranker instances with appropriate configurations.
    Supports provider-specific configs following the same pattern as other factories.
    """

    # Provider mappings with their config classes
    provider_to_class = {
        "cohere": ("ume.reranker.cohere_reranker.CohereReranker", CohereRerankerConfig),
        "sentence_transformer": (
            "ume.reranker.sentence_transformer_reranker.SentenceTransformerReranker",
            SentenceTransformerRerankerConfig,
        ),
        "zero_entropy": ("ume.reranker.zero_entropy_reranker.ZeroEntropyReranker", ZeroEntropyRerankerConfig),
        "llm_reranker": ("ume.reranker.llm_reranker.LLMReranker", LLMRerankerConfig),
        "huggingface": ("ume.reranker.huggingface_reranker.HuggingFaceReranker", HuggingFaceRerankerConfig),
    }

    @classmethod
    def create(cls, provider_name: str, config: Optional[Union[BaseRerankerConfig, Dict]] = None, **kwargs):
        """
        Create a reranker instance based on the provider and configuration.

        Args:
            provider_name: The reranker provider (e.g., 'cohere', 'sentence_transformer')
            config: Configuration object or dictionary
            **kwargs: Additional configuration parameters

        Returns:
            Reranker instance configured for the specified provider

        Raises:
            ImportError: If the provider class cannot be imported
            ValueError: If the provider is not supported
        """
        if provider_name not in cls.provider_to_class:
            raise ValueError(f"Unsupported reranker provider: {provider_name}")

        class_path, config_class = cls.provider_to_class[provider_name]

        # Handle configuration
        if config is None:
            config = config_class(**kwargs)
        elif isinstance(config, dict):
            config = config_class(**config, **kwargs)
        elif not isinstance(config, BaseRerankerConfig):
            raise ValueError(f"Config must be a {config_class.__name__} instance or dict")

        # Import and create the reranker class
        try:
            reranker_class = load_class(class_path)
        except (ImportError, AttributeError) as e:
            raise ImportError(f"Could not import reranker for provider '{provider_name}': {e}")

        return reranker_class(config)
