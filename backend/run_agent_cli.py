from __future__ import annotations

import asyncio
import sys

from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai.types import Content, Part

from app.agent import create_lucero_agent
from app.config import load_settings


async def main():
    print("==================================================")
    print("Lucero ADK Agent Local CLI Tester")
    print("==================================================")

    # 1. Get user query from args or prompt
    query = "What are the core inadmissibility grounds under CDJ processing?"
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])

    print(f"Executing Query: '{query}'\n")

    try:
        # 2. Bootstrap settings and agent
        settings = load_settings()
        agent = await create_lucero_agent()
        session_service = InMemorySessionService()

        # 3. Instantiate Runner
        runner = Runner(
            app_name="LuceroCLI",
            agent=agent,
            session_service=session_service,
            auto_create_session=True,
        )

        # 4. Prepare message structure
        user_message = Content(role="user", parts=[Part.from_text(text=query)])

        print("--- Stream Started ---")
        events = runner.run_async(
            user_id="cli_user",
            session_id="cli_session",
            new_message=user_message,
        )

        final_response = ""
        async for event in events:
            # Yield text parts as they arrive
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        print(part.text, end="", flush=True)
                        final_response += part.text

            # Inspect tool calls and logs
            func_calls = event.get_function_calls()
            if func_calls:
                print("\n[ADK Agent initiated Tool Call(s)]")
                for call in func_calls:
                    print(f"  └─► Tool: {call.name}")
                    if call.args:
                        print(f"      Arguments: {call.args}")

            func_responses = event.get_function_responses()
            if func_responses:
                print("\n[Tool Call Response(s) Received]")
                for resp in func_responses:
                    print(f"  └─◄ Tool: {resp.name}")

        print("\n--- Stream Finished ---")
        print("\n==================================================")
        print("Final Synthesized Answer:")
        print(final_response.strip())
        print("==================================================")

    except Exception as exc:
        print(f"\n[ERROR] Runner execution failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nAborted.")
