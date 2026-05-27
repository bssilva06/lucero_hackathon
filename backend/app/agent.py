from __future__ import annotations

import logging
from mcp import StdioServerParameters
from google.adk.agents import Agent
from google.adk.tools import FunctionTool
from google.adk.tools.mcp_tool import StdioConnectionParams, McpToolset
from app.config import load_settings, redact_secret
from app.retrieval import check_visa_bulletin, lookup_uscis_form, search_uscis_policy_manual

logger = logging.getLogger("lucero.agent")


async def create_lucero_agent() -> Agent:
    """Loads settings, initializes the MongoDB MCP server, fetches tools, and builds the Agent."""
    settings = load_settings()
    logger.info("Initializing Lucero ADK agent with model: %s", settings.gemini_reasoning_model)

    # Configure Stdio parameters for the MongoDB MCP server
    server_params = StdioServerParameters(
        command=settings.mcp_command,
        args=settings.mcp_args,
        env={"MDB_MCP_CONNECTION_STRING": settings.mdb_mcp_connection_string},
    )
    connection_params = StdioConnectionParams(server_params=server_params)

    # Initialize the MCP Toolset
    logger.info("Wired MCP connection string: %s", redact_secret(settings.mdb_mcp_connection_string))
    logger.info("Launching MongoDB MCP server: %s %s", settings.mcp_command, " ".join(settings.mcp_args))
    mcp_toolset = McpToolset(
        connection_params=connection_params,
        tool_filter=["aggregate", "find", "collection-schema", "collection-indexes"],
    )

    # Fetch tools from the MCP server
    logger.info("Connecting to MongoDB MCP server to fetch tools...")
    tools = await mcp_toolset.get_tools()
    logger.info("Fetched %d tools from MongoDB MCP server", len(tools))
    tools.append(FunctionTool(search_uscis_policy_manual))
    tools.append(FunctionTool(lookup_uscis_form))
    tools.append(FunctionTool(check_visa_bulletin))
    logger.info("Registered canonical retrieval tool: search_uscis_policy_manual")
    logger.info("Registered canonical form lookup tool: lookup_uscis_form")
    logger.info("Registered canonical visa bulletin tool: check_visa_bulletin")

    # Initialize the Google ADK Agent
    agent = Agent(
        name="lucero_agent",
        model=settings.gemini_reasoning_model,
        instruction=(
            "You are Lucero, a bilingual (English/Spanish) research co-pilot for immigration legal teams. "
            "Your domain is I-601A provisional unlawful presence waivers and Ciudad Juarez consular processing. "
            "\n\n"
            "CRITICAL INSTRUCTIONS:\n"
            "1. Ground every factual claim in retrieved source authority by invoking search_uscis_policy_manual, lookup_uscis_form, or the MongoDB MCP tools (e.g. aggregate or find).\n"
            "1a. Use lookup_uscis_form for USCIS filing fees, edition dates, filing locations, filing methods, and form-specific instructions. When citing fee facts from lookup_uscis_form, cite USCIS G-1055 explicitly and do not add fee components that are not present in the tool result.\n"
            "1b. Use check_visa_bulletin for Visa Bulletin category/country/month questions and identify both the DOS chart value and the USCIS chart selected for adjustment of status.\n"
            "2. Always cite your sources with relevant detail (e.g., Policy Manual section, CFR or INA section) and state the 'current as of' date if available.\n"
            "3. If the retrieved database documents do not contain the answer, say so explicitly and refuse to invent details from your parametric memory.\n"
            "4. Detect the language of the user's message and respond in that same language (English or Spanish).\n"
            "5. Strictly refuse outcome predictions (e.g., 'Will this be approved?'), strategic case advice, fake hardship letters, or advice on misrepresenting entry dates."
        ),
        tools=tools,
    )

    return agent
