import { withoutTrailingSlash } from '@ai-sdk/provider-utils'

import { UMEGenericLanguageModel } from './ume-generic-language-model'
import { UMEChatModelId, UMEChatSettings } from './ume-types'
import { UMEProviderSettings } from './ume-provider'

export class UME {
  readonly baseURL: string
  readonly headers?: any

  constructor(options: UMEProviderSettings = {
    provider: 'openai',
  }) {
    this.baseURL =
      withoutTrailingSlash(options.baseURL) ?? 'https://api.openai.com'

    this.headers = options.headers
  }

  private get baseConfig() {
    return {
      baseURL: this.baseURL,
      headers: this.headers,
    }
  }

  chat(modelId: UMEChatModelId, settings: UMEChatSettings = {}) {
    return new UMEGenericLanguageModel(modelId, settings, {
      provider: 'openai',
      modelType: 'chat',
      ...this.baseConfig,
    })
  }

  completion(modelId: UMEChatModelId, settings: UMEChatSettings = {}) {
    return new UMEGenericLanguageModel(modelId, settings, {
      provider: 'openai',
      modelType: 'completion',
      ...this.baseConfig,
    })
  }
}