"""MCP client: Streamable HTTP + permission checks + shared audit file with operator UI."""
from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import AsyncExitStack
from datetime import datetime
from pathlib import Path
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

logging.getLogger("mcp").setLevel(logging.WARNING)

# Streamable HTTP defaults use a 300s SSE read — wrong server on the port can look like an infinite hang.
_MCP_STREAM_TIMEOUT = float(os.environ.get("MCP_STREAM_READ_TIMEOUT", "45"))
_MCP_CONNECT_TIMEOUT = float(os.environ.get("MCP_CONNECT_TIMEOUT", "25"))
_MCP_RPC_TIMEOUT = float(os.environ.get("MCP_RPC_TIMEOUT", "45"))


class MCPPermissionHTTPClient:
    def __init__(self, server_url: str, permissions_file: str | Path):
        self.server_url = server_url.rstrip("/")
        self.permissions_file = Path(permissions_file)
        self.permissions_file.parent.mkdir(parents=True, exist_ok=True)
        self.audit_log_file = self.permissions_file.parent / "audit.log"
        self.exit_stack = AsyncExitStack()
        self.session: ClientSession | None = None
        self._connected = False
        self.permissions = self.load_permissions()

    def load_permissions(self) -> dict[str, Any]:
        if self.permissions_file.exists():
            return json.loads(self.permissions_file.read_text(encoding="utf-8"))
        return {
            "read_file": "allow",
            "write_file": "ask",
            "list_files": "allow",
            "delete_file": "deny",
            "execute_command": "deny",
            "analyze_code": "ask",
        }

    def save_permissions(self) -> None:
        self.permissions_file.write_text(
            json.dumps(self.permissions, indent=2), encoding="utf-8"
        )

    def reload_permissions(self) -> None:
        self.permissions = self.load_permissions()

    def check_permission(self, tool_name: str, arguments: dict) -> str:
        arg_key = f"{tool_name}:{json.dumps(arguments, sort_keys=True)}"
        if arg_key in self.permissions:
            return self.permissions[arg_key]
        return self.permissions.get(tool_name, "ask")

    def log_audit(self, operation: str, decision: str, reason: str = "") -> None:
        timestamp = datetime.now().isoformat()
        line = f"[{timestamp}] {operation} - Decision: {decision}"
        if reason:
            line += f" - Reason: {reason}"
        line += "\n"
        with open(self.audit_log_file, "a", encoding="utf-8") as f:
            f.write(line)

    async def _reset_connection(self) -> None:
        try:
            await self.exit_stack.aclose()
        except Exception:
            pass
        self.exit_stack = AsyncExitStack()
        self.session = None
        self._connected = False

    async def _rpc(self, awaitable):
        """Bound MCP session calls so a stuck server cannot hang the UI forever."""
        try:
            return await asyncio.wait_for(awaitable, timeout=_MCP_RPC_TIMEOUT)
        except TimeoutError:
            await self._reset_connection()
            raise

    async def _connect_impl(self) -> None:
        mcp_url = f"{self.server_url}/mcp"
        read, write, _ = await self.exit_stack.enter_async_context(
            streamablehttp_client(
                mcp_url,
                timeout=12.0,
                sse_read_timeout=_MCP_STREAM_TIMEOUT,
            )
        )
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(read, write)
        )
        assert self.session is not None
        await self.session.initialize()

    async def connect(self) -> None:
        if self._connected:
            return
        try:
            await asyncio.wait_for(self._connect_impl(), timeout=_MCP_CONNECT_TIMEOUT)
        except Exception:
            await self._reset_connection()
            raise
        self._connected = True

    async def list_tools(self):
        await self.connect()
        assert self.session is not None
        result = await self._rpc(self.session.list_tools())
        return result.tools

    async def call_tool(self, tool_name: str, arguments: dict | None = None):
        await self.connect()
        assert self.session is not None
        if arguments is None:
            arguments = {}
        result = await self._rpc(self.session.call_tool(tool_name, arguments))
        return result

    async def call_tool_with_permission(
        self,
        tool_name: str,
        arguments: dict | None = None,
        approved: bool = False,
    ):
        await self.connect()
        assert self.session is not None
        if arguments is None:
            arguments = {}

        self.reload_permissions()
        permission = self.check_permission(tool_name, arguments)

        if permission == "deny":
            self.log_audit(f"TOOL: {tool_name}", "DENIED", "Policy: deny")
            return [type("obj", (), {"text": f"Permission denied for tool: {tool_name}"})]

        if permission == "ask" and not approved:
            self.log_audit(f"TOOL: {tool_name}", "ASK", "Awaiting approval")
            approval_msg = f"""Permission required for tool: {tool_name}
Arguments: {json.dumps(arguments, indent=2)}

This tool requires approval before execution.
Reply approve in chat or use Approve in the operator console."""
            return [type("obj", (), {"text": approval_msg})]

        self.log_audit(f"TOOL: {tool_name}", "ALLOWED", f"Policy: {permission}")
        result = await self._rpc(
            self.session.call_tool(tool_name, arguments=arguments)
        )
        return result.content

    async def list_resource_templates(self):
        await self.connect()
        assert self.session is not None
        result = await self._rpc(self.session.list_resource_templates())
        return result.resourceTemplates

    async def read_resource(self, uri: str):
        await self.connect()
        assert self.session is not None
        result = await self._rpc(self.session.read_resource(uri=uri))
        return result.contents

    async def list_prompts(self):
        await self.connect()
        assert self.session is not None
        result = await self._rpc(self.session.list_prompts())
        return result.prompts

    async def get_prompt(self, prompt_name: str, arguments: dict | None = None):
        await self.connect()
        assert self.session is not None
        if arguments is None:
            arguments = {}
        str_args = {k: str(v) if not isinstance(v, str) else v for k, v in arguments.items()}
        result = await self._rpc(
            self.session.get_prompt(name=prompt_name, arguments=str_args)
        )
        return result.messages

    async def cleanup(self) -> None:
        await self._reset_connection()
