#!/usr/bin/env python3
"""Package the dependency-free Voicify MCP server for Claude Desktop."""

import json
import zipfile
from pathlib import Path


project = Path(__file__).resolve().parent.parent
manifest = project / "mcp" / "manifest.json"
server = project / "mcp" / "server.py"
version = json.loads(manifest.read_text(encoding="utf-8"))["version"]
output = project / "dist" / f"Voicify-MCP-{version}.mcpb"
output.parent.mkdir(parents=True, exist_ok=True)

with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
    bundle.write(manifest, "manifest.json")
    bundle.write(server, "mcp/server.py")

print(output)
