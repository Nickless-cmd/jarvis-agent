"""
Tool adapters for existing tools.py functions.
Registers all tools with the tool registry.
"""

from jarvis.agent_core.tool_registry import ToolSpec, register_tool
import jarvis.tools as tools


# Register all tools with appropriate specs

# System tools
register_tool(
    ToolSpec(
        name="system_info",
        description="Get system information (CPU, memory, disk, network)",
        args_schema={},
        risk_level="low"
    ),
    lambda: tools.system_info()
)

register_tool(
    ToolSpec(
        name="ping_host",
        description="Ping a host to check connectivity",
        args_schema={"host": {"type": "string", "description": "Host to ping"}},
        risk_level="low"
    ),
    lambda host: tools.ping_host(host)
)

register_tool(
    ToolSpec(
        name="list_processes",
        description="List running processes",
        args_schema={"limit": {"type": "integer", "description": "Maximum number of processes to return", "default": 10}},
        risk_level="medium"
    ),
    lambda limit=10: tools.list_processes(limit)
)

register_tool(
    ToolSpec(
        name="find_process",
        description="Find processes by name or command",
        args_schema={
            "query": {"type": "string", "description": "Search query"},
            "limit": {"type": "integer", "description": "Maximum number of results", "default": 5}
        },
        risk_level="medium"
    ),
    lambda query, limit=5: tools.find_process(query, limit)
)

# Search tools
register_tool(
    ToolSpec(
        name="news_search",
        description="Search for news articles",
        args_schema={"query": {"type": "string", "description": "Search query"}},
        risk_level="low"
    ),
    lambda query: tools.news_combined(query)
)

register_tool(
    ToolSpec(
        name="web_search",
        description="Search the web using DuckDuckGo and Google",
        args_schema={"query": {"type": "string", "description": "Search query"}},
        risk_level="low"
    ),
    lambda query: tools.web_search(query)
)

register_tool(
    ToolSpec(
        name="search_combined",
        description="Combined search across multiple sources",
        args_schema={
            "query": {"type": "string", "description": "Search query"},
            "max_items": {"type": "integer", "description": "Maximum items per source", "default": 8}
        },
        risk_level="low"
    ),
    lambda query, max_items=8: tools.search_combined(query, max_items)
)

# Weather tools
register_tool(
    ToolSpec(
        name="weather_now",
        description="Get current weather for a city",
        args_schema={"city": {"type": "string", "description": "City name"}},
        risk_level="low"
    ),
    lambda city: tools.weather_now(city)
)

register_tool(
    ToolSpec(
        name="weather_forecast",
        description="Get weather forecast for a city",
        args_schema={"city": {"type": "string", "description": "City name"}},
        risk_level="low"
    ),
    lambda city: tools.weather_forecast(city)
)

# Utility tools
register_tool(
    ToolSpec(
        name="time_now",
        description="Get current date/time",
        args_schema={},
        risk_level="low",
    ),
    lambda: tools.time_now()
)

register_tool(
    ToolSpec(
        name="currency_convert",
        description="Convert currency amounts",
        args_schema={
            "frm": {"type": "string", "description": "From currency code"},
            "to": {"type": "string", "description": "To currency code"},
            "amount": {"type": "number", "description": "Amount to convert", "default": 1}
        },
        risk_level="low"
    ),
    lambda frm, to, amount=1: tools.currency_convert(frm, to, amount)
)

register_tool(
    ToolSpec(
        name="kill_process",
        description="Kill a process by PID",
        args_schema={"pid": {"type": "integer", "description": "Process ID to kill"}},
        risk_level="high"
    ),
    lambda pid: tools.kill_process(pid)
)

register_tool(
    ToolSpec(
        name="read_article",
        description="Read and extract text content from a web article",
        args_schema={"url": {"type": "string", "description": "Article URL to read"}},
        risk_level="low"
    ),
    lambda url: tools.read_article(url)
)
