import asyncio

import pytest

from mcp import Client

import filesystem_mcp_server
from filesystem_mcp_server import mcp
from matching_agent import run_matching


@pytest.mark.anyio
async def test_list_files():
    async with Client(mcp) as client:

        result = await client.call_tool(
            "list_files",
            {
                "directory": ".",
                "extensions": [".txt"],
            },
        )

        assert not result.is_error
        assert result.structured_content is not None


@pytest.mark.anyio
async def test_batch_process():
    async with Client(mcp) as client:

        result = await client.call_tool(
            "batch_process",
            {
                "files": [
                    "rahul_resume.txt",
                    "priya_resume.txt",
                ],
            },
        )

        assert not result.is_error
        assert result.structured_content is not None


@pytest.mark.anyio
async def test_resource_discovery():
    async with Client(mcp) as client:

        resources = await client.list_resources()

        uris = {
            str(resource.uri)
            for resource in resources.resources
        }

        assert "filesystem://config" in uris

        templates = await client.list_resource_templates()
        template_uris = {
            template.uri_template
            for template in templates.resource_templates
        }
        assert "filesystem://file/{path}" in template_uris
        assert "filesystem://directory/{directory}" in template_uris


@pytest.mark.anyio
async def test_missing_file():
    async with Client(mcp) as client:

        result = await client.call_tool(
            "read_file",
            {
                "path": "does_not_exist.txt"
            },
        )

        assert result.is_error


@pytest.mark.anyio
async def test_metadata_and_path_traversal():
    async with Client(mcp) as client:
        metadata = await client.call_tool(
            "get_file_metadata",
            {"path": "rahul_resume.txt"},
        )
        assert not metadata.is_error
        assert metadata.structured_content["sha256"]

        traversal = await client.call_tool(
            "read_file",
            {"path": "../requirements.txt"},
        )
        assert traversal.is_error


@pytest.mark.anyio
async def test_watch_directory_detects_new_resume(tmp_path, monkeypatch):
    monkeypatch.setattr(filesystem_mcp_server, "RESUME_DIRECTORY", tmp_path)
    monkeypatch.setattr(filesystem_mcp_server, "WATCH_INTERVAL", 0.01)

    async with Client(mcp) as client:
        watch_task = asyncio.create_task(
            client.call_tool(
                "watch_directory",
                {"directory": ".", "duration_seconds": 2},
            )
        )
        await asyncio.sleep(0.05)
        (tmp_path / "incoming.txt").write_text("Candidate", encoding="utf-8")
        result = await watch_task

        assert not result.is_error
        assert result.structured_content["result"][0]["path"] == "incoming.txt"


@pytest.mark.anyio
async def test_agent_uses_mcp_workflow():
    results = await run_matching("React Node.js TypeScript")

    assert results
    assert all(result.name for result in results)
    assert all(0 <= result.score <= 100 for result in results)
