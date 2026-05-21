from __future__ import annotations

import os
import shutil
import subprocess

from app.config import load_settings


def main() -> int:
    settings = load_settings()

    print("Lucero Phase 1 MongoDB MCP smoke test")
    print("-------------------------------------")

    command_path = shutil.which(settings.mcp_command)
    if not command_path:
        print(f"FAIL {settings.mcp_command} was not found.")
        print("     Install Node.js 20+ and globally install mongodb-mcp-server, or set LUCERO_MCP_COMMAND.")
        return 1

    print(f"PASS MCP launcher found: {command_path}")
    print("Starting MongoDB MCP server briefly to verify it can launch...")

    env = os.environ.copy()
    env["MDB_MCP_CONNECTION_STRING"] = settings.mdb_mcp_connection_string

    try:
        process = subprocess.Popen(
            [command_path, *settings.mcp_args],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            stdout, stderr = process.communicate(timeout=8)
        except subprocess.TimeoutExpired:
            process.terminate()
            print("PASS MongoDB MCP server launched and stayed running for 8 seconds.")
            print("     This is enough for the Phase 1 local launch check.")
            return 0
    except OSError as exc:
        print("FAIL Could not start MongoDB MCP server.")
        print(f"Reason: {exc}")
        return 1

    combined_output = "\n".join(part for part in [stdout, stderr] if part).strip()
    if process.returncode == 0:
        print("PASS MongoDB MCP command completed successfully.")
        return 0

    print("FAIL MongoDB MCP command exited early.")
    print(f"Exit code: {process.returncode}")
    if combined_output:
        print("Output:")
        print(combined_output[-2_000:])
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
