from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ResourceNotFoundError

from config import (
    ALLOWED_EXTENSIONS,
    MAX_BATCH_FILES,
    RESUME_DIRECTORY,
    WATCH_INTERVAL,
)


mcp = MCPServer(
    "filesystem-resume-server",
    instructions=(
        "Filesystem MCP server for resume discovery, reading, batch processing, "
        "directory watching, and resource discovery."
    ),
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_safe_path(relative_path: str) -> Path:
    """
    Resolve a path inside the configured resume directory.

    Prevents clients from escaping the configured directory.
    """
    base = RESUME_DIRECTORY.resolve()
    target = (base / relative_path).resolve()

    try:
        target.relative_to(base)
    except ValueError:
        raise ValueError("Path is outside the configured resume directory.")

    return target


def file_metadata(path: Path) -> dict[str, Any]:
    stat = path.stat()

    return {
        "name": path.name,
        "path": str(path.relative_to(RESUME_DIRECTORY)),
        "size": stat.st_size,
        "modified_at": stat.st_mtime,
        "extension": path.suffix.lower(),
    }


def calculate_file_hash(path: Path) -> str:
    sha256 = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            sha256.update(chunk)

    return sha256.hexdigest()


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def list_files(
    directory: str = ".",
    extensions: list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    List files inside a directory.

    Args:
        directory: Relative directory inside the configured resume directory.
        extensions: Optional extension filter such as [".pdf", ".txt"].
    """
    target = get_safe_path(directory)

    if not target.exists():
        raise FileNotFoundError(f"Directory does not exist: {directory}")

    if not target.is_dir():
        raise NotADirectoryError(f"Not a directory: {directory}")

    normalized_extensions = None

    if extensions:
        normalized_extensions = {
            ext.lower() if ext.startswith(".") else f".{ext.lower()}"
            for ext in extensions
        }

    results = []

    for path in sorted(target.iterdir()):
        if not path.is_file():
            continue

        if normalized_extensions and path.suffix.lower() not in normalized_extensions:
            continue

        results.append(file_metadata(path))

    return results


@mcp.tool()
def read_file(path: str) -> str:
    """
    Read a text file from the configured resume directory.
    """
    target = get_safe_path(path)

    if not target.exists():
        raise FileNotFoundError(f"File does not exist: {path}")

    if not target.is_file():
        raise ValueError(f"Path is not a file: {path}")

    try:
        return target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise ValueError(
            f"File is not UTF-8 text: {path}. "
            "Use a document extraction tool for binary PDFs/DOCX files."
        )


@mcp.tool()
def get_file_metadata(path: str) -> dict[str, Any]:
    """
    Return metadata for a file.
    """
    target = get_safe_path(path)

    if not target.exists():
        raise FileNotFoundError(f"File does not exist: {path}")

    if not target.is_file():
        raise ValueError(f"Path is not a file: {path}")

    metadata = file_metadata(target)
    metadata["sha256"] = calculate_file_hash(target)

    return metadata


@mcp.tool()
def batch_process(
    files: list[str],
) -> list[dict[str, Any]]:
    """
    Process multiple resume files efficiently.

    Returns metadata and text for each supported text file.
    """
    if not files:
        return []

    if len(files) > MAX_BATCH_FILES:
        raise ValueError(
            f"Too many files. Maximum allowed is {MAX_BATCH_FILES}."
        )

    results = []

    for file_path in files:
        target = get_safe_path(file_path)

        if not target.exists():
            results.append({
                "path": file_path,
                "status": "error",
                "error": "file_not_found",
            })
            continue

        if not target.is_file():
            results.append({
                "path": file_path,
                "status": "error",
                "error": "not_a_file",
            })
            continue

        try:
            content = target.read_text(encoding="utf-8")

            results.append({
                "path": file_path,
                "status": "success",
                "name": target.name,
                "content": content,
                "metadata": file_metadata(target),
            })

        except UnicodeDecodeError:
            results.append({
                "path": file_path,
                "status": "error",
                "error": "binary_file_not_supported_by_text_reader",
            })

    return results


@mcp.tool()
def watch_directory(
    directory: str = ".",
    duration_seconds: int = 10,
) -> list[dict[str, Any]]:
    """
    Monitor a directory for newly created files.

    The function polls the directory for the requested duration and
    returns newly discovered files.
    """
    if duration_seconds < 1:
        raise ValueError("duration_seconds must be at least 1.")

    target = get_safe_path(directory)

    if not target.exists():
        raise FileNotFoundError(f"Directory does not exist: {directory}")

    if not target.is_dir():
        raise NotADirectoryError(f"Not a directory: {directory}")

    initial_files = {
        str(path.resolve())
        for path in target.iterdir()
        if path.is_file()
    }

    discovered = []

    start = time.time()

    while time.time() - start < duration_seconds:
        current_files = {
            str(path.resolve())
            for path in target.iterdir()
            if path.is_file()
        }

        new_files = current_files - initial_files

        for file_path in sorted(new_files):
            path = Path(file_path)

            if path.suffix.lower() not in ALLOWED_EXTENSIONS:
                continue

            discovered.append(
                {
                    "event": "created",
                    "name": path.name,
                    "path": str(path.relative_to(RESUME_DIRECTORY)),
                    "extension": path.suffix.lower(),
                }
            )

        if discovered:
            break

        time.sleep(WATCH_INTERVAL)

    return discovered


# ---------------------------------------------------------------------------
# MCP Resources
# ---------------------------------------------------------------------------

@mcp.resource("filesystem://config")
def filesystem_config() -> str:
    """
    Expose server configuration as an MCP resource.
    """
    config = {
        "resume_directory": str(RESUME_DIRECTORY),
        "allowed_extensions": sorted(ALLOWED_EXTENSIONS),
        "watch_interval": WATCH_INTERVAL,
        "max_batch_files": MAX_BATCH_FILES,
    }

    return json.dumps(config, indent=2)


@mcp.resource("filesystem://file/{path}")
def file_resource(path: str) -> str:
    """
    Expose a text file as an MCP resource.
    """
    target = get_safe_path(path)

    if not target.exists():
        raise ResourceNotFoundError(f"File does not exist: {path}")

    if not target.is_file():
        raise ResourceNotFoundError(f"Not a file: {path}")

    try:
        return target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise ValueError(f"File is not a UTF-8 text file: {path}")


@mcp.resource("filesystem://directory/{directory}")
def directory_resource(directory: str) -> str:
    """
    Expose directory listing as an MCP resource.
    """
    files = list_files(directory)

    return json.dumps(
        {
            "directory": directory,
            "files": files,
        },
        indent=2,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    RESUME_DIRECTORY.mkdir(parents=True, exist_ok=True)

    # stdio is ideal for a local MCP client integration/demo.
    try:
        mcp.run(transport="stdio")
    except KeyboardInterrupt:
        pass
