# UME - The Memory Layer for Your AI Apps

UME is a self-improving memory layer for LLM applications, enabling personalized AI experiences that save costs and delight users. We offer both cloud and open-source solutions to cater to different needs.

See the complete [OSS Docs](https://docs.ume.ai/open-source/node-quickstart).
See the complete [Platform API Reference](https://docs.ume.ai/api-reference).

## 1. Installation

For the open-source version, you can install the UME package using npm:

```bash
npm i ume
```

## 2. API Key Setup

For the cloud offering, sign in to [UME Platform](https://app.ume.ai/dashboard/api-keys?utm_source=oss&utm_medium=ume-ts-readme) to obtain your API Key.

## 3. Client Features

### Cloud Offering

The cloud version provides a comprehensive set of features, including:

- **Memory Operations**: Perform CRUD operations on memories.
- **Search Capabilities**: Search for relevant memories using advanced filters.
- **Memory History**: Track changes to memories over time.
- **Error Handling**: Robust error handling for API-related issues.
- **Async/Await Support**: All methods return promises for easy integration.

### Open-Source Offering

The open-source version includes the following top features:

- **Memory Management**: Add, update, delete, and retrieve memories.
- **Vector Store Integration**: Supports various vector store providers for efficient memory retrieval.
- **LLM Support**: Integrates with multiple LLM providers for generating responses.
- **Customizable Configuration**: Easily configure memory settings and providers.
- **SQLite Storage**: Use SQLite for memory history management.

## 4. Memory Operations

UME provides a simple and customizable interface for performing memory operations. You can create long-term and short-term memories, search for relevant memories, and manage memory history.

## 5. Error Handling

The MemoryClient throws errors for any API-related issues. You can catch and handle these errors effectively.

## 6. Using with async/await

All methods of the MemoryClient return promises, allowing for seamless integration with async/await syntax.

## 7. Testing the Client

To test the MemoryClient in a Node.js environment, you can create a simple script to verify the functionality of memory operations.

## Getting Help

If you have any questions or need assistance, please reach out to us:

- Email: founders@ume.ai
- [Join our discord community](https://ume.ai/discord)
- GitHub Issues: [Report bugs or request features](https://github.com/fengjutian/UME/issues)
