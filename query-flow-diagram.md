# RAG System Query Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                  FRONTEND                                    │
│                              (script.js)                                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                    User types: "What is MCP?"
                                     │
                                     ▼
                    ┌────────────────────────────────┐
                    │   sendMessage()                │
                    │   - Disable input              │
                    │   - Show loading animation     │
                    │   - Display user message       │
                    └────────────────────────────────┘
                                     │
                                     │ POST /api/query
                                     │ { query: "What is MCP?",
                                     │   session_id: "session_1" }
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              BACKEND - API LAYER                             │
│                                (app.py)                                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                    ┌────────────────────────────────┐
                    │  @app.post("/api/query")       │
                    │  - Parse request               │
                    │  - Create/get session          │
                    └────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           RAG SYSTEM ORCHESTRATOR                            │
│                             (rag_system.py)                                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                    ┌────────────────────────────────┐
                    │  rag_system.query()            │
                    │  1. Build prompt               │
                    │  2. Get conversation history   │
                    │  3. Prepare tools              │
                    └────────────────────────────────┘
                                     │
                    ┌────────────────┴────────────────┐
                    ▼                                 ▼
        ┌──────────────────────┐         ┌──────────────────────┐
        │  SessionManager      │         │  ToolManager         │
        │  - Get history       │         │  - Get tool defs     │
        │  - Last 5 exchanges  │         │  - search_course_    │
        └──────────────────────┘         │    content           │
                    │                    └──────────────────────┘
                    │                                 │
                    └────────────────┬────────────────┘
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          AI GENERATOR - FIRST CALL                           │
│                            (ai_generator.py)                                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                    ┌────────────────────────────────────────┐
                    │  client.messages.create()              │
                    │  - system: SYSTEM_PROMPT + history     │
                    │  - messages: [user query]              │
                    │  - tools: [search_course_content]      │
                    │  - tool_choice: auto                   │
                    └────────────────────────────────────────┘
                                     │
                                     │ Call to Anthropic API
                                     ▼
                    ┌────────────────────────────────────────┐
                    │       CLAUDE API (Anthropic)           │
                    │  Analyzes: "This needs course search"  │
                    └────────────────────────────────────────┘
                                     │
                                     │ Response: stop_reason = "tool_use"
                                     ▼
                    ┌────────────────────────────────────────┐
                    │  Tool Use Block:                       │
                    │  {                                     │
                    │    type: "tool_use",                   │
                    │    name: "search_course_content",      │
                    │    input: {                            │
                    │      query: "MCP",                     │
                    │      course_name: null,                │
                    │      lesson_number: null               │
                    │    }                                   │
                    │  }                                     │
                    └────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            TOOL EXECUTION LAYER                              │
│                           (search_tools.py)                                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                    ┌────────────────────────────────────────┐
                    │  ToolManager.execute_tool()            │
                    │  → CourseSearchTool.execute()          │
                    │    - query: "MCP"                      │
                    │    - course_name: null                 │
                    │    - lesson_number: null               │
                    └────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           VECTOR STORE LAYER                                 │
│                            (vector_store.py)                                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                    ┌────────────────────────────────────────┐
                    │  VectorStore.search()                  │
                    │  - Encode query to embedding           │
                    │  - Apply filters (if any)              │
                    └────────────────────────────────────────┘
                                     │
                                     ▼
                    ┌────────────────────────────────────────┐
                    │         ChromaDB                       │
                    │  Collection: course_content            │
                    │  - Semantic vector search              │
                    │  - Cosine similarity                   │
                    │  - Return top 5 chunks                 │
                    └────────────────────────────────────────┘
                                     │
                                     │ Results with metadata
                                     ▼
                    ┌────────────────────────────────────────┐
                    │  SearchResults Object:                 │
                    │  documents: [                          │
                    │    "Course Intro to MCP Lesson 1...",  │
                    │    "MCP stands for Model Context..."   │
                    │  ]                                     │
                    │  metadata: [                           │
                    │    {course_title: "Intro to MCP",      │
                    │     lesson_number: 1},                 │
                    │    ...                                 │
                    │  ]                                     │
                    │  distances: [0.23, 0.45, ...]          │
                    └────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         BACK TO TOOL LAYER                                   │
│                         (search_tools.py)                                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                    ┌────────────────────────────────────────┐
                    │  _format_results()                     │
                    │  - Add [Course - Lesson N] headers     │
                    │  - Store sources in last_sources       │
                    │  - Return formatted string             │
                    └────────────────────────────────────────┘
                                     │
                                     │ Formatted tool result
                                     ▼
                    ┌────────────────────────────────────────┐
                    │  Tool Result:                          │
                    │  "[Intro to MCP - Lesson 1]            │
                    │   MCP stands for Model Context         │
                    │   Protocol...                          │
                    │                                        │
                    │   [Advanced MCP - Lesson 3]            │
                    │   MCP enables servers to..."           │
                    └────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AI GENERATOR - SECOND CALL                           │
│                            (ai_generator.py)                                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                    ┌────────────────────────────────────────┐
                    │  _handle_tool_execution()              │
                    │  - Build message history:              │
                    │    1. User: "What is MCP?"             │
                    │    2. Assistant: [tool_use block]      │
                    │    3. User: [tool_result block]        │
                    └────────────────────────────────────────┘
                                     │
                                     │ Call to Anthropic API
                                     ▼
                    ┌────────────────────────────────────────┐
                    │       CLAUDE API (Anthropic)           │
                    │  Synthesizes answer from search        │
                    │  results based on system prompt        │
                    └────────────────────────────────────────┘
                                     │
                                     │ Final response
                                     ▼
                    ┌────────────────────────────────────────┐
                    │  Response:                             │
                    │  "MCP (Model Context Protocol) is a    │
                    │   standardized protocol that enables   │
                    │   AI applications to connect with      │
                    │   external data sources..."            │
                    └────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         BACK TO RAG SYSTEM                                   │
│                           (rag_system.py)                                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                    ┌────────────────────────────────────────┐
                    │  Post-processing:                      │
                    │  1. Extract sources from ToolManager   │
                    │  2. Update SessionManager with         │
                    │     query + response                   │
                    │  3. Reset sources                      │
                    └────────────────────────────────────────┘
                                     │
                    ┌────────────────┴────────────────┐
                    ▼                                 ▼
        ┌──────────────────────┐         ┌──────────────────────┐
        │  ToolManager         │         │  SessionManager      │
        │  last_sources: [     │         │  sessions: {         │
        │    "Intro to MCP -   │         │    "session_1": [    │
        │     Lesson 1"        │         │      {role: "user",  │
        │  ]                   │         │       content: "..."},│
        └──────────────────────┘         │      {role: "asst",  │
                                         │       content: "..."}│
                                         │    ]                 │
                                         │  }                   │
                                         └──────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         BACK TO API LAYER                                    │
│                            (app.py)                                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                    ┌────────────────────────────────────────┐
                    │  Return QueryResponse:                 │
                    │  {                                     │
                    │    answer: "MCP (Model Context...",    │
                    │    sources: ["Intro to MCP - Lesson 1"],│
                    │    session_id: "session_1"             │
                    │  }                                     │
                    └────────────────────────────────────────┘
                                     │
                                     │ HTTP 200 JSON Response
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              BACK TO FRONTEND                                │
│                              (script.js)                                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                    ┌────────────────────────────────────────┐
                    │  Response handling:                    │
                    │  1. Remove loading animation           │
                    │  2. Parse markdown (marked.parse)      │
                    │  3. Create message div                 │
                    │  4. Add collapsible sources            │
                    │  5. Append to chat                     │
                    │  6. Re-enable input                    │
                    │  7. Store session_id                   │
                    └────────────────────────────────────────┘
                                     │
                                     ▼
                    ┌────────────────────────────────────────┐
                    │         USER SEES RESPONSE             │
                    │                                        │
                    │  💬 MCP (Model Context Protocol) is    │
                    │     a standardized protocol...         │
                    │                                        │
                    │  📚 Sources ▼                          │
                    │     Intro to MCP - Lesson 1            │
                    └────────────────────────────────────────┘


═══════════════════════════════════════════════════════════════════════════════

KEY COMPONENTS:

┌──────────────────┐
│  Frontend        │  JavaScript, HTML/CSS, marked.js for markdown
└──────────────────┘

┌──────────────────┐
│  API Layer       │  FastAPI, Pydantic models, CORS middleware
└──────────────────┘

┌──────────────────┐
│  RAG System      │  Orchestrates document processing, search, AI generation
└──────────────────┘

┌──────────────────┐
│  SessionManager  │  Maintains conversation history (max 5 exchanges)
└──────────────────┘

┌──────────────────┐
│  ToolManager     │  Manages tools available to Claude
└──────────────────┘

┌──────────────────┐
│  AI Generator    │  Anthropic Claude API integration with tool calling
└──────────────────┘

┌──────────────────┐
│  SearchTool      │  Executes searches, formats results, tracks sources
└──────────────────┘

┌──────────────────┐
│  VectorStore     │  ChromaDB interface for semantic search
└──────────────────┘

┌──────────────────┐
│  ChromaDB        │  Persistent vector database with sentence-transformers
└──────────────────┘

═══════════════════════════════════════════════════════════════════════════════

IMPORTANT NOTES:

1. **Two-Phase AI Generation**:
   - Phase 1: Claude decides if it needs to search
   - Phase 2: Claude synthesizes answer from search results

2. **Tool-Based RAG**:
   - Claude autonomously calls search tool (not always retrieving)
   - Better for general knowledge vs. course-specific questions

3. **Semantic Search**:
   - Uses sentence-transformers for embeddings
   - ChromaDB performs cosine similarity search
   - Returns top 5 most relevant chunks

4. **Session Management**:
   - Keeps last 5 Q&A exchanges in memory
   - Provides conversation context to Claude
   - Enables multi-turn conversations

5. **Source Tracking**:
   - Search tool stores sources during formatting
   - Sources passed back through the entire chain
   - Displayed in collapsible UI element

═══════════════════════════════════════════════════════════════════════════════
```
