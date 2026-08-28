import asyncio
import time
from pathlib import Path

from mcp_client import MCPFilesystemClient


async def main():
    client = MCPFilesystemClient()

    # Start watching in the background.
    watch_task = asyncio.create_task(
        run_watch()
    )

    await asyncio.sleep(2)

    demo_path = Path("resumes") / f"demo_candidate_{int(time.time())}.txt"
    demo_path.write_text(
        """
New Candidate

Full Stack Developer
3 years experience
React
Node.js
MongoDB
TypeScript
Docker
Git
""",
        encoding="utf-8",
    )

    result = await watch_task

    print("\nWATCH RESULT:")
    print(result)


async def run_watch():
    # We use a direct MCP client connection here.
    from mcp import Client, StdioServerParameters
    from pathlib import Path

    server = Path("filesystem_mcp_server.py").resolve()

    params = StdioServerParameters(
        command="python",
        args=[str(server)],
    )

    async with Client(params) as client:
        result = await client.call_tool(
            "watch_directory",
            {
                "directory": ".",
                "duration_seconds": 5,
            },
        )

        if result.is_error:
            raise RuntimeError(str(result.content))

        return result.structured_content


if __name__ == "__main__":
    asyncio.run(main())
