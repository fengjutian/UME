import { UMEProviderSettings } from "./ume-provider";
import { OpenAIProviderSettings } from "@ai-sdk/openai";
import { AnthropicProviderSettings } from "@ai-sdk/anthropic";
import { CohereProviderSettings } from "@ai-sdk/cohere";
import { GroqProviderSettings } from "@ai-sdk/groq";
import { GoogleGenerativeAIProviderSettings } from "@ai-sdk/google";
export type UMEChatModelId =
  | (string & NonNullable<unknown>);

export interface UMEConfigSettings {
  user_id?: string;
  app_id?: string;
  agent_id?: string;
  run_id?: string;
  metadata?: Record<string, any>;
  filters?: Record<string, any>;
  infer?: boolean;
  page?: number;
  page_size?: number;
  umeApiKey?: string;
  top_k?: number;
  threshold?: number;
  rerank?: boolean;
  host?: string;
}

export interface UMEChatConfig extends UMEConfigSettings, UMEProviderSettings {}

export type LLMProviderSettings = OpenAIProviderSettings | AnthropicProviderSettings | CohereProviderSettings | GroqProviderSettings | GoogleGenerativeAIProviderSettings;

export interface UMEConfig extends UMEConfigSettings {}
export interface UMEChatSettings extends UMEConfigSettings {}
