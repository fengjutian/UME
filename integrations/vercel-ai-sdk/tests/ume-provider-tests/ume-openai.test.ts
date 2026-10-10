import dotenv from "dotenv";
dotenv.config();

import { createUME } from "../../src";
import { generateText } from "ai";
import { LanguageModelV3Prompt } from '@ai-sdk/provider';
import { testConfig } from "../../config/test-config";

describe("OPENAI UME Tests", () => {
  const { userId } = testConfig;
  jest.setTimeout(30000);
  let ume: any;

  beforeEach(() => {
    ume = createUME({
      provider: "openai",
      apiKey: process.env.OPENAI_API_KEY,
      umeConfig: {
        user_id: userId
      }
    });
  });

  it("should retrieve memories and generate text using UME OpenAI provider", async () => {
    const messages: LanguageModelV3Prompt = [
      {
        role: "user",
        content: [
          { type: "text", text: "Suggest me a good car to buy." },
          { type: "text", text: " Write only the car name and it's color." },
        ],
      },
    ];
    
    const { text } = await generateText({
      model: ume("gpt-4-turbo"),
      messages: messages
    });

    // Expect text to be a string
    expect(typeof text).toBe('string');
    expect(text.length).toBeGreaterThan(0);
  });

  it("should generate text using openai provider with memories", async () => {
    const prompt = "Suggest me a good car to buy.";

    const { text } = await generateText({
      model: ume("gpt-4-turbo"),
      prompt: prompt
    });

    expect(typeof text).toBe('string');
    expect(text.length).toBeGreaterThan(0);
  });
});