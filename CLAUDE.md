# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Course Materials RAG (Retrieval-Augmented Generation) System** that answers questions about course materials using semantic search and AI-powered responses. It's a full-stack application with a Python FastAPI backend and vanilla JavaScript frontend.

## Development Commands

### Setup
```bash
# Install dependencies
uv sync

# Setup environment (required)
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

### Running the Application
```bash
# Quick start (recommended)
./run.sh

# Manual start
cd backend
uv run uvicorn app:app --reload --port 8000
```

The application runs on `http://localhost:8000` with API docs at `http://localhost:8000/docs`.

### Code Quality
```bash
# Install dev dependencies (includes black, ruff, mypy)
uv sync --extra dev

# Auto-format and fix code
./format.sh

# Run quality checks (formatting, linting, type checking)
./quality.sh

# Individual commands
uv run black backend/              # Format code
uv run black --check backend/      # Check formatting without changes
uv run ruff check backend/         # Lint code
uv run ruff check --fix backend/   # Auto-fix linting issues
uv run mypy backend/               # Type check
```

**Quality Tools:**
- **Black**: Code formatter (line length: 100)
- **Ruff**: Fast linter with auto-fix (replaces flake8, isort, pyupgrade)
- **Mypy**: Static type checker

### Prerequisites
- Python 3.13+
- uv package manager
- Anthropic API key

## Architecture Overview

### RAG Pipeline Flow

The system uses a **two-phase tool-based RAG approach** where Claude autonomously decides when to search:

1. **User Query** → Frontend (`script.js`) POSTs to `/api/query`
2. **RAGSystem** (`rag_system.py`) orchestrates the pipeline:
   - Retrieves conversation history from `SessionManager`
   - Calls `AIGenerator` with search tool available
3. **First Claude API Call** (`ai_generator.py`):
   - Claude analyzes query and decides whether to use `search_course_content` tool
   - Returns `tool_use` if search needed
4. **Tool Execution** (`search_tools.py`):
   - `CourseSearchTool` performs semantic search via `VectorStore`
   - ChromaDB does cosine similarity search on embeddings
   - Returns top-k chunks with metadata
5. **Second Claude API Call**:
   - Claude synthesizes answer from search results
   - Follows system prompt to be concise and educational
6. **Response** → Sources tracked, history updated, JSON returned to frontend

### Key Components

**Backend (`/backend`):**
- `app.py` - FastAPI app with two main endpoints: `/api/query`, `/api/courses`
- `rag_system.py` - **Main orchestrator** that coordinates all components
- `ai_generator.py` - Anthropic Claude API integration with tool calling support
- `document_processor.py` - Parses course docs and chunks text (sentence-based with overlap)
- `vector_store.py` - ChromaDB interface with two collections: `course_catalog` (metadata) and `course_content` (chunks)
- `search_tools.py` - Tool abstraction for Claude: `CourseSearchTool` implements search + formatting
- `session_manager.py` - Maintains conversation history (default: last 2 exchanges)
- `config.py` - Centralized configuration (chunk size, model, etc.)
- `models.py` - Pydantic/dataclass models: `Course`, `Lesson`, `CourseChunk`

**Frontend (`/frontend`):**
- `index.html` - Single-page chat interface
- `script.js` - Handles API calls, markdown rendering (marked.js), message display
- `style.css` - UI styling

### Document Format

Course documents in `/docs` must follow this structure:
```
Course Title: [title]
Course Link: [url]
Course Instructor: [name]

Lesson 0: Introduction
Lesson Link: [url]
[lesson content...]

Lesson 1: Next Topic
[lesson content...]
```

Documents are:
1. Parsed to extract course/lesson metadata
2. Chunked using sentence-based splitting (800 chars, 100 overlap)
3. Stored in ChromaDB with embeddings (sentence-transformers: `all-MiniLM-L6-v2`)
4. Indexed for semantic search

### Vector Store Architecture

**Two ChromaDB Collections:**

1. **`course_catalog`** - Course metadata for fuzzy course name matching
   - ID: course title
   - Metadata: instructor, links, lessons (JSON serialized)
   - Enables: "Find course matching 'MCP'" → resolves to exact title

2. **`course_content`** - Actual searchable content chunks
   - ID: `{course_title}_{chunk_index}`
   - Metadata: `course_title`, `lesson_number`, `chunk_index`
   - Chunks include context prefix: `"Course {title} Lesson {n} content: {text}"`

**Search Flow:**
```python
# If course_name provided, first resolve it semantically
course_title = _resolve_course_name(course_name)  # Uses course_catalog

# Then search content with filters
results = course_content.query(
    query_texts=[query],
    n_results=MAX_RESULTS,
    where={"course_title": course_title, "lesson_number": lesson_num}
)
```

### Tool-Based RAG (Not Traditional Retrieve-Always)

Unlike traditional RAG, this system uses **Anthropic's tool calling**:

- Claude has access to `search_course_content` tool definition
- System prompt instructs: "Use tool for course-specific questions, general knowledge doesn't need search"
- Tool returns formatted results: `[Course - Lesson N]\n{content}`
- Sources tracked in `CourseSearchTool.last_sources` for UI display

**Why this matters:** Claude can answer "What is Python?" without searching, but "What does Lesson 3 say about MCP?" triggers search.

### Configuration Settings (`config.py`)

Key settings:
- `ANTHROPIC_MODEL`: `"claude-sonnet-4-20250514"`
- `EMBEDDING_MODEL`: `"all-MiniLM-L6-v2"` (sentence-transformers)
- `CHUNK_SIZE`: 800 characters
- `CHUNK_OVERLAP`: 100 characters
- `MAX_RESULTS`: 5 search results
- `MAX_HISTORY`: 2 exchanges (4 messages)
- `CHROMA_PATH`: `"./chroma_db"` (persistent vector DB)

### Session Management

- Sessions created on first query if no `session_id` provided
- History format: `"User: {query}\nAssistant: {response}"`
- Included in Claude's system prompt for context
- Limited to last N exchanges (configurable via `MAX_HISTORY`)
- Auto-trimmed when limit exceeded

### Startup Behavior

On app startup (`@app.on_event("startup")`):
- Automatically loads all documents from `../docs` folder
- Skips already-indexed courses (checks existing titles in vector store)
- **Does NOT clear existing data** (`clear_existing=False`)

### Important Implementation Details

1. **Chunk Context Enrichment**: Last lesson's chunks get prefix `"Course {title} Lesson {n} content: {chunk}"` for better retrieval

2. **Sentence-Based Chunking**: Uses regex `(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\!|\?)\s+(?=[A-Z])` to avoid splitting on abbreviations

3. **Tool Result Formatting**: Search results formatted with headers before sending to Claude:
   ```
   [Course Title - Lesson 1]
   {chunk content}

   [Course Title - Lesson 3]
   {chunk content}
   ```

4. **Two-Pass Search**: Course name resolution (if provided) uses vector search on catalog, then filters content search by exact title

5. **Source Persistence**: Sources stored in tool during formatting, retrieved after response generation, then reset for next query

## Working with This Codebase

### Adding New Tools for Claude

1. Create tool class inheriting from `Tool` ABC in `search_tools.py`
2. Implement `get_tool_definition()` returning Anthropic tool schema
3. Implement `execute(**kwargs)` with tool logic
4. Register in `RAGSystem.__init__`: `self.tool_manager.register_tool(YourTool(...))`

### Modifying Document Processing

- Chunk size/overlap in `config.py`
- Parsing logic in `document_processor.py:process_course_document()`
- Embedding model in `config.py:EMBEDDING_MODEL`

### Changing AI Behavior

- System prompt in `ai_generator.py:SYSTEM_PROMPT`
- Model/temperature/max_tokens in `ai_generator.py:__init__` and `config.py`
- Tool usage instructions in system prompt

### Adding New API Endpoints

1. Add Pydantic models in `app.py` or `models.py`
2. Define endpoint in `app.py`
3. Use `rag_system` instance to access components
4. Update frontend `script.js` to call new endpoint

### Database Persistence

ChromaDB data persists in `./chroma_db/` directory (relative to where server runs). To reset:
```python
rag_system.vector_store.clear_all_data()
```

Or delete the directory manually and restart.
- always use uv to run the server do not use pip directly
- make sure to use uv to manage all dependencies
- use uv to run Python files.