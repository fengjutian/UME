# UME Integration Patterns

Working code examples for integrating UME Platform with popular AI frameworks.
All examples use `MemoryClient` (Platform API key).

Code examples are sourced from official UME integration docs at docs.ume.ai, simplified for quick reference.

---

## Common Pattern

Every integration follows the same 3-step loop:

1. **Retrieve** -- search relevant memories before generating a response
2. **Generate** -- include memories as context in the LLM prompt
3. **Store** -- save the interaction back to UME for future use

---

## LangChain

Source: [docs.ume.ai/integrations/langchain](https://docs.ume.ai/integrations/langchain)

```python
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from ume import MemoryClient

llm = ChatOpenAI(model="gpt-5-mini")
ume = MemoryClient()

prompt = ChatPromptTemplate.from_messages([
    SystemMessage(content="You are a helpful travel agent AI. Use the provided context to personalize your responses."),
    MessagesPlaceholder(variable_name="context"),
    HumanMessage(content="{input}")
])

def retrieve_context(query: str, user_id: str):
    """Retrieve relevant memories from UME"""
    memories = ume.search(query, filters={"user_id": user_id})
    memory_list = memories['results']
    serialized = ' '.join([m["memory"] for m in memory_list])
    return [
        {"role": "system", "content": f"Relevant information: {serialized}"},
        {"role": "user", "content": query}
    ]

def chat_turn(user_input: str, user_id: str) -> str:
    # 1. Retrieve
    context = retrieve_context(user_input, user_id)
    # 2. Generate
    chain = prompt | llm
    response = chain.invoke({"context": context, "input": user_input})
    # 3. Store
    ume.add(
        [{"role": "user", "content": user_input}, {"role": "assistant", "content": response.content}],
        user_id=user_id
    )
    return response.content
```

---

## CrewAI

Source: [docs.ume.ai/integrations/crewai](https://docs.ume.ai/integrations/crewai)

Install: `pip install crewai crewai-tools ume`

Newer CrewAI versions removed the `memory_config={"provider": "ume"}` shortcut on `Crew(...)`. Wire UME in explicitly through `MemoryClient` (retrieve, inject into the task, store). CrewAI's own `ExternalMemory` API is the native alternative; see the [CrewAI memory docs](https://docs.crewai.com/en/concepts/memory) for the shape your version expects.

```python
from crewai import Agent, Task, Crew, Process
from ume import MemoryClient

client = MemoryClient()

messages = [
    {"role": "user", "content": "I am more of a beach person than a mountain person."},
    {"role": "assistant", "content": "Noted! I'll recommend beach destinations."},
    {"role": "user", "content": "I like Airbnb more than hotels."},
]
client.add(messages, user_id="crew_user_1")

def get_user_context(user_id: str, query: str) -> str:
    results = client.search(query, filters={"user_id": user_id}).get("results", [])
    return "\n".join(f"- {m['memory']}" for m in results)

def plan_trip(destination: str, user_id: str):
    travel_agent = Agent(
        role="Personalized Travel Planner",
        goal="Plan personalized travel itineraries",
        backstory="You are a seasoned travel planner.",
    )
    user_context = get_user_context(user_id, f"travel preferences for {destination}")
    task = Task(
        description=f"""Find places to live, eat, and visit in {destination}.

        Known preferences for this user:
        {user_context or "No stored preferences yet."}
        """,
        expected_output=f"A detailed list of places to live, eat, and visit in {destination}.",
        agent=travel_agent,
    )
    crew = Crew(agents=[travel_agent], tasks=[task], process=Process.sequential)
    result = crew.kickoff()
    client.add([{"role": "user", "content": f"Planned a trip to {destination}."}], user_id=user_id)
    return result

result = plan_trip("San Francisco", "crew_user_1")
```

`add()` is asynchronous on the Platform, so the seed memories above are not searchable the instant it returns and a `plan_trip` call straight after it can see no preferences. Run the seeding in an earlier session, or wait until the `add` event is `SUCCEEDED` (poll `GET /v1/event/{event_id}/`) before the first `plan_trip`. The `add` at the end of `plan_trip` only writes, so it needs no wait.

---

## Vercel AI SDK

> **Dedicated skill available.** For comprehensive Vercel AI SDK documentation, see the [ume-vercel-ai-sdk skill](../../ume-vercel-ai-sdk/SKILL.md) ([GitHub](https://github.com/fengjutian/UME/tree/main/skills/ume-vercel-ai-sdk)).

Install: `npm install @ume/vercel-ai-provider`

Quick example (wrapped model with automatic memory):

```typescript
import { generateText } from "ai";
import { createUME } from "@ume/vercel-ai-provider";

const ume = createUME();
const { text } = await generateText({
    model: ume("gpt-5-mini", { user_id: "borat" }),
    prompt: "Suggest me a good car to buy!",
});
```

Supported providers: `openai`, `anthropic`, `google`, `groq`, `cohere`

---

## OpenAI Agents SDK

Source: [docs.ume.ai/integrations/openai-agents-sdk](https://docs.ume.ai/integrations/openai-agents-sdk)

```python
from agents import Agent, Runner, function_tool
from ume import MemoryClient

ume = MemoryClient()

@function_tool
def search_memory(query: str, user_id: str) -> str:
    """Search through past conversations and memories"""
    memories = ume.search(query, filters={"user_id": user_id}, top_k=3)
    if memories and memories.get('results'):
        return "\n".join([f"- {mem['memory']}" for mem in memories['results']])
    return "No relevant memories found."

@function_tool
def save_memory(content: str, user_id: str) -> str:
    """Save important information to memory"""
    ume.add([{"role": "user", "content": content}], user_id=user_id)
    return "Information saved to memory."

agent = Agent(
    name="Personal Assistant",
    instructions="""You are a helpful personal assistant with memory capabilities.
    Use search_memory to recall past conversations.
    Use save_memory to store important information.""",
    tools=[search_memory, save_memory],
    model="gpt-5-mini"
)

result = Runner.run_sync(agent, "I love Italian food and I'm planning a trip to Rome next month")
print(result.final_output)
```

### Multi-Agent with Handoffs

```python
from agents import Agent, Runner, function_tool

travel_agent = Agent(
    name="Travel Planner",
    instructions="You are a travel planning specialist. Use search_memory and save_memory tools.",
    tools=[search_memory, save_memory],
    model="gpt-5-mini"
)

health_agent = Agent(
    name="Health Advisor",
    instructions="You are a health and wellness advisor. Use search_memory and save_memory tools.",
    tools=[search_memory, save_memory],
    model="gpt-5-mini"
)

triage_agent = Agent(
    name="Personal Assistant",
    instructions="""Route travel questions to Travel Planner, health questions to Health Advisor.""",
    handoffs=[travel_agent, health_agent],
    model="gpt-5-mini"
)

result = Runner.run_sync(triage_agent, "Plan a healthy meal for my Italy trip")
```

---

## Pipecat (Voice / Real-Time)

Source: [docs.ume.ai/integrations/pipecat](https://docs.ume.ai/integrations/pipecat)

Install: `pip install "pipecat-ai[ume]"`

```python
import os

from pipecat.services.ume import UMEMemoryService

memory = UMEMemoryService(
    api_key=os.getenv("UME_API_KEY"),
    user_id="alice",
    agent_id="voice_bot",
    params={
        "search_limit": 10,
        "search_threshold": 0.1,
        "system_prompt": "Here are your past memories:",
        "add_as_system_message": True,
    }
)

# Use in pipeline
pipeline = Pipeline([
    transport.input(),
    stt,
    user_context,
    memory,          # Memory enhances context automatically
    llm,
    transport.output(),
    assistant_context
])
```

---

## LangGraph

Source: [docs.ume.ai/integrations/langgraph](https://docs.ume.ai/integrations/langgraph)

State-based agent workflows with memory persistence. Best for complex conversation flows with branching logic.

```python
from typing import Annotated, TypedDict, List
from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langchain_openai import ChatOpenAI
from ume import MemoryClient
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

llm = ChatOpenAI(model="gpt-5-mini")
ume = MemoryClient()

class State(TypedDict):
    messages: Annotated[List[HumanMessage | AIMessage], add_messages]
    ume_user_id: str

def chatbot(state: State):
    messages = state["messages"]
    user_id = state["ume_user_id"]

    # Retrieve relevant memories
    memories = ume.search(messages[-1].content, filters={"user_id": user_id})
    context = "Relevant context:\n"
    for memory in memories["results"]:
        context += f"- {memory['memory']}\n"

    system_message = SystemMessage(content=f"""You are a helpful support assistant.
{context}""")

    response = llm.invoke([system_message] + messages)

    # Store the interaction
    ume.add(
        [{"role": "user", "content": messages[-1].content},
         {"role": "assistant", "content": response.content}],
        user_id=user_id
    )
    return {"messages": [response]}

graph = StateGraph(State)
graph.add_node("chatbot", chatbot)
graph.add_edge(START, "chatbot")
app = graph.compile()

# Usage
result = app.invoke({
    "messages": [HumanMessage(content="I need help with my order")],
    "ume_user_id": "customer_123"
})
```

---

## LlamaIndex

Source: [docs.ume.ai/integrations/llama-index](https://docs.ume.ai/integrations/llama-index)

Install: `pip install llama-index-core llama-index-memory-ume`

LlamaIndex has native UME support via `UMEMemory`. Works with ReAct and FunctionCalling agents.

```python
from llama_index.memory.ume import UMEMemory

context = {"user_id": "alice", "agent_id": "llama_agent_1"}
memory = UMEMemory.from_client(
    context=context,
    search_msg_limit=4,  # messages from chat history used for retrieval (default: 5)
)

# Use with LlamaIndex agent
from llama_index.core.agent import FunctionCallingAgent
from llama_index.llms.openai import OpenAI

llm = OpenAI(model="gpt-5-mini")
agent = FunctionCallingAgent.from_tools(
    tools=[],
    llm=llm,
    memory=memory,
    verbose=True,
)

response = agent.chat("I prefer vegetarian restaurants")
# Memory automatically stores and retrieves context
response = agent.chat("What kind of food do I like?")
# Agent retrieves the vegetarian preference from UME
```

---

## AutoGen

Source: [docs.ume.ai/integrations/autogen](https://docs.ume.ai/integrations/autogen)

Install: `pip install autogen ume`

Multi-agent conversational systems with memory persistence.

```python
import os

from autogen import ConversableAgent
from ume import MemoryClient

memory_client = MemoryClient()
USER_ID = "alice"

agent = ConversableAgent(
    "chatbot",
    llm_config={"config_list": [{"model": "gpt-5-mini", "api_key": os.environ["OPENAI_API_KEY"]}]},
    code_execution_config=False,
    human_input_mode="NEVER",
)

def get_context_aware_response(question: str) -> str:
    # Retrieve memories for context
    relevant_memories = memory_client.search(question, filters={"user_id": USER_ID})
    context = "\n".join([m["memory"] for m in relevant_memories.get("results", [])])

    prompt = f"""Answer considering previous interactions:
    Previous context: {context}
    Question: {question}"""

    reply = agent.generate_reply(messages=[{"content": prompt, "role": "user"}])

    # Store the new interaction
    memory_client.add(
        [{"role": "user", "content": question}, {"role": "assistant", "content": reply}],
        user_id=USER_ID
    )
    return reply
```

---

## All Supported Frameworks

Beyond the examples above, UME integrates with:

| Framework | Type | Install |
|-----------|------|---------|
| [Mastra](https://docs.ume.ai/integrations/mastra) | TS agent framework | `npm install @mastra/core @mastra/ume @ai-sdk/openai zod` |
| [ElevenLabs](https://docs.ume.ai/integrations/elevenlabs) | Voice AI | `pip install elevenlabs ume` |
| [LiveKit](https://docs.ume.ai/integrations/livekit) | Real-time voice/video | `pip install livekit-agents ume` |
| [Camel AI](https://docs.ume.ai/integrations/camel-ai) | Multi-agent framework | `pip install "camel-ai>=0.2.0" ume` |
| [AWS Bedrock](https://docs.ume.ai/integrations/aws-bedrock) | Cloud LLM provider | `pip install ume boto3 opensearch-py` |
| [Dify](https://docs.ume.ai/integrations/dify) | Low-code AI platform | Plugin-based |
| [Google AI ADK](https://docs.ume.ai/integrations/google-ai-adk) | Google agent framework | `pip install google-adk ume` |
| [Agno](https://docs.ume.ai/integrations/agno) | Multimodal agent framework | `pip install agno ume` |
| [Strands Agents](https://docs.ume.ai/integrations/strands) | AWS agent SDK (native `MemoryStore`) | `pip install ume-strands` |
| [LangChain Tools](https://docs.ume.ai/integrations/langchain-tools) | UME tools for any LangChain agent | `pip install langchain_core ume` |

For the general Python pattern (no framework), see the "Common integration pattern" in [SKILL.md](../SKILL.md).
