# Architecture Overview

- **Server**: FastAPI app (jarvis.server)
- **Agent**: Handles user queries, tool orchestration, and memory
- **Tool runner/registry**: Manages available tools and their execution
- **Event bus/store**: In-memory and persistent event handling
- **UI**: Static frontend (HTML/JS/CSS in ui/)
