import { UMEProviderSettings } from "./ume-provider";
import UMETextGenerator, { ProviderSettings } from "./provider-response-provider";
import { LanguageModelV3 } from '@ai-sdk/provider';

class UMEClassSelector {
    modelId: string;
    provider_wrapper: string;
    config: UMEProviderSettings;
    provider_config?: ProviderSettings;
    static supportedProviders = ["openai", "anthropic", "cohere", "groq", "google", "gemini"];

    constructor(modelId: string, config: UMEProviderSettings, provider_config?: ProviderSettings) {
        this.modelId = modelId;
        this.provider_wrapper = config.provider || "openai";
        this.provider_config = provider_config;
        if(config) this.config = config;
        else this.config = {
            provider: this.provider_wrapper,
        };

        // Check if provider_wrapper is supported
        if (!UMEClassSelector.supportedProviders.includes(this.provider_wrapper)) {
            throw new Error(`Model not supported: ${this.provider_wrapper}`);
        }
    }

    createProvider(): LanguageModelV3 {
        return new UMETextGenerator(this.modelId, this.config , this.provider_config || {});
    }
}

export { UMEClassSelector };
