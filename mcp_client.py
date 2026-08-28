from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

from mcp import Client, StdioServerParameters


SERVER_PATH = Path(__file__).resolve().parent / "filesystem_mcp_server.py"


class MCPFilesystemClient:
    """
    Client wrapper used by the matching agent.

    The agent never directly touches the filesystem.
    """

    def __init__(self, server_path: Path = SERVER_PATH):
        self.server_path = server_path

    async def _connect(self):
        params = StdioServerParameters(
            command=sys.executable,
            args=[str(self.server_path)],
        )

        return Client(params)

    async def list_files(
        self,
        directory: str = ".",
        extensions: list[str] | None = None,
    ) -> Any:
        async with await self._connect() as client:
            arguments = {
                "directory": directory,
                "extensions": extensions,
            }

            result = await client.call_tool(
                "list_files",
                arguments,
            )

            if result.is_error:
                raise RuntimeError(str(result.content))

            return result.structured_content["result"]

    async def read_file(self, path: str) -> Any:
        async with await self._connect() as client:
            result = await client.call_tool(
                "read_file",
                {"path": path},
            )

            if result.is_error:
                raise RuntimeError(str(result.content))

            return result.structured_content["result"]

    async def batch_process(self, files: list[str]) -> Any:
        async with await self._connect() as client:
            result = await client.call_tool(
                "batch_process",
                {"files": files},
            )

            if result.is_error:
                raise RuntimeError(str(result.content))

            return result.structured_content["result"]

    async def get_file_metadata(self, path: str) -> Any:
        async with await self._connect() as client:
            result = await client.call_tool(
                "get_file_metadata",
                {"path": path},
            )

            if result.is_error:
                raise RuntimeError(str(result.content))

            return result.structured_content["result"]

    async def watch_directory(
        self,
        directory: str = ".",
        duration_seconds: int = 10,
    ) -> Any:
        async with await self._connect() as client:
            result = await client.call_tool(
                "watch_directory",
                {
                    "directory": directory,
                    "duration_seconds": duration_seconds,
                },
            )

            if result.is_error:
                raise RuntimeError(str(result.content))

            return result.structured_content["result"]

    async def get_tools(self) -> list[str]:
        async with await self._connect() as client:
            tools = await client.list_tools()

            return [
                tool.name
                for tool in tools.tools
            ]

    async def get_resources(self) -> list[str]:
        async with await self._connect() as client:
            resources = await client.list_resources()

            return [
                str(resource.uri)
                for resource in resources.resources
            ]

    async def get_resource_templates(self) -> list[str]:
        async with await self._connect() as client:
            templates = await client.list_resource_templates()

            return [
                template.uri_template
                for template in templates.resource_templates
            ]


async def main():
    client = MCPFilesystemClient()

    print("Available MCP tools:")
    tools = await client.get_tools()

    for tool in tools:
        print(f"  - {tool}")

    print("\nAvailable MCP resources:")
    resources = await client.get_resources()

    for resource in resources:
        print(f"  - {resource}")

    print("\nResume files:")
    files = await client.list_files(
        extensions=[".txt"]
    )

    print(files)


if __name__ == "__main__":
    asyncio.run(main())
