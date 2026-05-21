from __future__ import annotations

import asyncio
import json
from typing import Any

from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams
from mcp import StdioServerParameters

from app.config import load_settings


async def _main() -> int:
    settings = load_settings()

    print("Lucero MongoDB MCP retrieval smoke test")
    print("--------------------------------------")
    print(f"Database: {settings.mongo_db}")
    print(f"Collection: {settings.mongo_chunks_collection}")

    toolset = McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command=settings.mcp_command,
                args=settings.mcp_args,
                env={"MDB_MCP_CONNECTION_STRING": settings.mdb_mcp_connection_string},
            )
        ),
        tool_filter=["find", "aggregate", "collection-schema", "collection-indexes"],
    )

    try:
        tools = await toolset.get_tools()
        tool_names = sorted(tool.name for tool in tools)
        print(f"Tools: {', '.join(tool_names)}")

        find_tool = _get_tool(tools, "find")
        aggregate_tool = _get_tool(tools, "aggregate")

        find_result = await _call_tool(
            find_tool,
            {
                "database": settings.mongo_db,
                "collection": settings.mongo_chunks_collection,
                "filter": {"ingestion_run_id": "fixture-smoke-test", "status": "active"},
                "limit": 2,
            },
        )
        aggregate_result = await _call_tool(
            aggregate_tool,
            {
                "database": settings.mongo_db,
                "collection": settings.mongo_chunks_collection,
                "pipeline": [
                    {"$match": {"ingestion_run_id": "fixture-smoke-test", "status": "active"}},
                    {"$group": {"_id": "$agency", "count": {"$sum": 1}}},
                    {"$sort": {"_id": 1}},
                ],
            },
        )
    except Exception as exc:
        print("FAIL MCP retrieval smoke test failed.")
        print(f"Reason: {exc}")
        return 1
    finally:
        await toolset.close()

    find_text = _stringify(find_result)
    aggregate_text = _stringify(aggregate_result)

    if "fixture-smoke-test" not in find_text:
        print("FAIL MCP find did not return fixture documents.")
        print(find_text[:2_000])
        return 1

    if "USCIS" not in aggregate_text and "DOS" not in aggregate_text:
        print("FAIL MCP aggregate did not return expected agency groups.")
        print(aggregate_text[:2_000])
        return 1

    print("PASS MCP find returned fixture documents.")
    print("PASS MCP aggregate returned fixture groups.")
    print()
    print("Find result preview:")
    print(find_text[:1_000])
    print()
    print("Aggregate result preview:")
    print(aggregate_text[:1_000])
    return 0


def _get_tool(tools: list[Any], name: str) -> Any:
    for tool in tools:
        if tool.name == name:
            return tool
    raise RuntimeError(f"MCP tool not found: {name}")


async def _call_tool(tool: Any, args: dict[str, Any]) -> Any:
    if hasattr(tool, "run_async"):
        return await tool.run_async(args=args, tool_context=None)
    if hasattr(tool, "call"):
        result = tool.call(args)
        if hasattr(result, "__await__"):
            return await result
        return result
    raise RuntimeError(f"Don't know how to call tool: {tool}")


def _stringify(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, default=str, indent=2, sort_keys=True)
    except TypeError:
        return str(value)


def main() -> int:
    return asyncio.run(_main())


if __name__ == "__main__":
    raise SystemExit(main())
