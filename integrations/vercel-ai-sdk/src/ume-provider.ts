import { ProviderV3 } from '@ai-sdk/provider';
import { LanguageModelV3 } from '@ai-sdk/provider';
import { withoutTrailingSlash } from "@ai-sdk/provider-utils";
import { UMEChatModelId, UMEChatSettings, UMEConfig } from "./ume-types";
import { UMEGenericLanguageModel } from "./ume-generic-language-model";
import { LLMProviderSettings } from "./ume-types";

export interface UMEProvider extends ProviderV3 {
  (modelId: UMEChatModelId, settings?: UMEChatSettings): LanguageModelV3;

  chat(modelId: UMEChatModelId, settings?: UMEChatSettings): LanguageModelV3;
  completion(modelId: UMEChatModelId, settings?: UMEChatSettings): LanguageModelV3;

  languageModel(
    modelId: UMEChatModelId,
    settings?: UMEChatSettings
  ): LanguageModelV3;
}

export interface UMEProviderSettings {
  baseURL?: string;
  /**
   * Custom fetch implementation. You can use it as a middleware to intercept
   * requests or to provide a custom fetch implementation for e.g. testing
   */
  fetch?: typeof fetch;
  /**
   * @internal
   */
  generateId?: () => string;
  /**
   * Custom headers to include in the requests.
   */
  headers?: Record<string, string | undefined>;
  name?: string;
  umeApiKey?: string;
  apiKey?: string;
  provider?: string;
  modelType?: "completion" | "chat";
  umeConfig?: UMEConfig;

  /**
   * The configuration for the provider.
   */
  config?: LLMProviderSettings ;
}

export function createUME(
  options: UMEProviderSettings = {
    provider: "openai",
  }
): UMEProvider {
  const baseURL =
    withoutTrailingSlash(options.baseURL) ?? "https://api.openai.com";
  const getHeaders = () => ({
    ...options.headers,
  });

  const createGenericModel = (
    modelId: UMEChatModelId,
    settings: UMEChatSettings = {}
  ) =>
    new UMEGenericLanguageModel(
      modelId,
      settings,
      {
        baseURL,
        fetch: options.fetch,
        headers: getHeaders(),
        provider: options.provider || "openai",
        name: options.name,
        umeApiKey: options.umeApiKey,
        apiKey: options.apiKey,
        umeConfig: options.umeConfig,
      },
      options.config
    );

  const createCompletionModel = (
    modelId: UMEChatModelId,
    settings: UMEChatSettings = {}
  ) =>
    new UMEGenericLanguageModel(
      modelId,
      settings,
      {
        baseURL,
        fetch: options.fetch,
        headers: getHeaders(),
        provider: options.provider || "openai",
        name: options.name,
        umeApiKey: options.umeApiKey,
        apiKey: options.apiKey,
        umeConfig: options.umeConfig,
        modelType: "completion",
      },
      options.config
    );

  const createChatModel = (
    modelId: UMEChatModelId,
    settings: UMEChatSettings = {}
  ) =>
    new UMEGenericLanguageModel(
      modelId,
      settings,
      {
        baseURL,
        fetch: options.fetch,
        headers: getHeaders(),
        provider: options.provider || "openai",
        name: options.name,
        umeApiKey: options.umeApiKey,
        apiKey: options.apiKey,
        umeConfig: options.umeConfig,
        modelType: "chat",
      },
      options.config
    );

  const provider = function (
    modelId: UMEChatModelId,
    settings: UMEChatSettings = {}
  ) {
    if (new.target) {
      throw new Error(
        "The UME model function cannot be called with the new keyword."
      );
    }

    return createGenericModel(modelId, settings);
  };

  provider.specificationVersion = 'v3';
  provider.languageModel = createGenericModel;
  provider.completion = createCompletionModel;
  provider.chat = createChatModel;

  return provider as unknown as UMEProvider;
}

export const ume = createUME();
