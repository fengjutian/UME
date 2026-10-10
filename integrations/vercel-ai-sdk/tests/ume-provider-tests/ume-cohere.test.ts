import dotenv from "dotenv";
dotenv.config();

import { createUME, retrieveMemories } from "../../src";
import { generateText } from "ai";
import { LanguageModelV3Prompt } from '@ai-sdk/provider';
import { testConfig } from "../../config/test-config";
import { createCohere } from "@ai-sdk/cohere";

describe("COHERE UME Tests", () => {
  const { userId } = testConfig;
  jest.setTimeout(30000);
  let ume: any;

  beforeEach(() => {
    ume = createUME({
      provider: "cohere",
      apiKey: process.env.COHERE_API_KEY,
      umeConfig: {
        user_id: userId
      }
    });
  });

  it("should retrieve memories and generate text using COHERE provider", async () => {
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
      // @ts-ignore
      model: ume("command-r-plus"),
      messages: messages
    });

    // Expect text to be a string
    expect(typeof text).toBe('string');
    expect(text.length).toBeGreaterThan(0);
  });

  it("should generate text using COHERE provider with memories", async () => {
    const prompt = "Suggest me a good car to buy.";

    const { text } = await generateText({
      // @ts-ignore
      model: ume("command-r-plus"),
      prompt: prompt
    });

    expect(typeof text).toBe('string');
    expect(text.length).toBeGreaterThan(0);
  });
});