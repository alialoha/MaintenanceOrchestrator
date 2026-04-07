"""LLM + MCP (HTTP) host logic — no Gradio; shared by operator UI and Flask (OpenAI client today)."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from openai import OpenAI

from agent.llm_client import build_llm_client, resolved_llm_model
from mcp_client.http_permission_client import MCPPermissionHTTPClient


def risk_levels_map() -> dict[str, str]:
    levels = {
        "read_file": "low",
        "list_files": "low",
        "write_file": "medium",
        "analyze_code": "medium",
        "delete_file": "high",
        "execute_command": "critical",
        # Phase-1 maintenance orchestrator tools
        "fetch_vehicle_faults": "low",
        "lookup_fault_resolution": "low",
        "score_fault_severity": "medium",
        "get_maintenance_history": "low",
        "predict_maintenance_need": "medium",
        "create_work_order": "high",
        "request_approval": "high",
        "record_decision_log": "medium",
        "get_audit_trail": "low",
        "estimate_repair_duration": "medium",
        "check_parts_inventory": "low",
        "propose_service_appointment": "medium",
        "reserve_service_slot": "high",
        "list_deliveries_at_risk": "low",
        "estimate_delay_impact": "medium",
        "generate_operator_summary": "low",
        "generate_customer_update": "low",
    }
    return levels


class MCPLLMHost(MCPPermissionHTTPClient):
    """Tool-calling assistant over streamable HTTP MCP with client-side permissions."""

    def __init__(self, server_url: str | None = None, permissions_file: str | None = None):
        base = Path(__file__).resolve().parents[2]
        data_dir = Path(os.environ.get("MCP_DATA_DIR", base / "data"))
        url = server_url or os.environ.get("MCP_SERVER_URL", "http://127.0.0.1:8000")
        perm = permissions_file or os.environ.get(
            "PERMISSIONS_PATH", str(data_dir / "permissions.json")
        )
        super().__init__(url, perm)
        self._llm_client: OpenAI | None = None
        self.model = resolved_llm_model()
        self.conversation_history: list[dict[str, Any]] = []
        self.pending_approval: dict[str, Any] | None = None
        self.risk_levels = risk_levels_map()

    @property
    def llm_client(self) -> OpenAI:
        if self._llm_client is None:
            self._llm_client = build_llm_client()
        return self._llm_client

    def reset_conversation(self) -> None:
        self.conversation_history = []
        self.pending_approval = None

    async def get_available_tools(self):
        await self.connect()
        mcp_tools = await self.list_tools()
        openai_tools = []
        self.reload_permissions()
        for tool in mcp_tools:
            tool_schema = {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or f"Execute {tool.name}",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
            permission = self.permissions.get(tool.name, "ask")
            risk = self.risk_levels.get(tool.name, "medium")
            tool_schema["function"]["description"] += (
                f" (Permission: {permission}, Risk: {risk})"
            )
            if hasattr(tool, "inputSchema") and tool.inputSchema:
                schema = tool.inputSchema
                if isinstance(schema, dict):
                    if "properties" in schema:
                        tool_schema["function"]["parameters"]["properties"] = schema["properties"]
                    if "required" in schema and schema["required"]:
                        tool_schema["function"]["parameters"]["required"] = schema["required"]
            openai_tools.append(tool_schema)

        openai_tools.extend(
            [
                {
                    "type": "function",
                    "function": {
                        "name": "mcp_list_resources",
                        "description": "List resource templates from the MCP server",
                        "parameters": {"type": "object", "properties": {}},
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "mcp_read_resource",
                        "description": "Read a resource by URI",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "uri": {
                                    "type": "string",
                                    "description": "Resource URI",
                                }
                            },
                            "required": ["uri"],
                        },
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "mcp_list_prompts",
                        "description": "List prompt templates from the MCP server",
                        "parameters": {"type": "object", "properties": {}},
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "mcp_get_prompt",
                        "description": "Render a prompt template by name",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "arguments": {"type": "object"},
                            },
                            "required": ["name"],
                        },
                    },
                },
            ]
        )
        return openai_tools

    async def execute_tool(self, tool_name: str, arguments: dict):
        await self.connect()

        if tool_name == "mcp_list_resources":
            templates = await self.list_resource_templates()
            out = "Resource templates:\n"
            for t in templates:
                out += f"- {getattr(t, 'uriTemplate', getattr(t, 'uri', '?'))}\n"
            return out

        if tool_name == "mcp_read_resource":
            uri = arguments.get("uri")
            if not uri:
                return "Error: uri required"
            contents = await self.read_resource(uri)
            if contents and len(contents) > 0:
                c = contents[0]
                return getattr(c, "text", str(c))
            return str(contents)

        if tool_name == "mcp_list_prompts":
            prompts = await self.list_prompts()
            lines = []
            for p in prompts:
                desc = (getattr(p, "description", None) or "").strip()
                if desc:
                    lines.append(f"- {p.name}\n  {desc}")
                else:
                    lines.append(f"- {p.name}")
            return "\n".join(lines) if lines else "No prompts"

        if tool_name == "mcp_get_prompt":
            name = arguments.get("name")
            pargs = arguments.get("arguments") or {}
            if not name:
                return "Error: name required"
            messages = await self.get_prompt(name, pargs)
            parts = []
            for msg in messages:
                role = getattr(msg, "role", "?")
                content = getattr(msg, "content", "")
                if hasattr(content, "text"):
                    content = content.text
                parts.append(f"{role}: {content}")
            return "\n".join(parts)

        result = await self.call_tool_with_permission(tool_name, arguments)
        if isinstance(result, list) and result:
            content = result[0]
            if hasattr(content, "text"):
                return content.text
            return str(content)
        return str(result)

    def assess_risk(self, tool_name: str, arguments: dict) -> dict:
        risk_level = self.risk_levels.get(tool_name, "medium")
        self.reload_permissions()
        permission = self.permissions.get(tool_name, "ask")
        return {
            "tool": tool_name,
            "risk_level": risk_level,
            "permission": permission,
            "requires_approval": permission in ("ask", "deny"),
            "description": "",
        }

    async def chat(self, user_message: str, history: list | None = None):
        await self.connect()
        self.reload_permissions()

        if self.pending_approval and user_message.strip().lower() in (
            "yes",
            "approve",
            "ok",
            "confirm",
            "y",
        ):
            tool_name = self.pending_approval["tool_name"]
            arguments = self.pending_approval["arguments"]
            self.pending_approval = None
            result = await self.call_tool_with_permission(
                tool_name, arguments, approved=True
            )
            text = self._tool_result_text(result)
            self.conversation_history.append({"role": "user", "content": user_message})
            self.conversation_history.append({"role": "assistant", "content": text})
            return text

        if self.pending_approval and user_message.strip().lower() in (
            "no",
            "deny",
            "cancel",
            "n",
        ):
            self.pending_approval = None
            msg = "Operation cancelled."
            self.conversation_history.append({"role": "user", "content": user_message})
            self.conversation_history.append({"role": "assistant", "content": msg})
            return msg

        self.conversation_history.append({"role": "user", "content": user_message})
        tools = await self.get_available_tools()

        if tools:
            response = self.llm_client.chat.completions.create(
                model=self.model,
                messages=self.conversation_history,
                tools=tools,
                tool_choice="auto",
            )
        else:
            response = self.llm_client.chat.completions.create(
                model=self.model, messages=self.conversation_history
            )

        if not response or not response.choices:
            return "Error: No response from LLM"

        assistant_message = response.choices[0].message
        if assistant_message.tool_calls:
            self.conversation_history.append(
                {
                    "role": "assistant",
                    "content": assistant_message.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in assistant_message.tool_calls
                    ],
                }
            )
            for tc in assistant_message.tool_calls:
                fname = tc.function.name
                fargs = json.loads(tc.function.arguments)
                tool_result = await self.execute_tool(fname, fargs)
                if (
                    "Permission required for tool:" in str(tool_result)
                    and "approve" in str(tool_result).lower()
                ):
                    self.pending_approval = {"tool_name": fname, "arguments": fargs}
                self.conversation_history.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": str(tool_result),
                    }
                )
            final = self.llm_client.chat.completions.create(
                model=self.model, messages=self.conversation_history
            )
            if not final or not final.choices:
                return "Error: No response after tools"
            final_text = final.choices[0].message.content or ""
            self.conversation_history.append(
                {"role": "assistant", "content": final_text}
            )
            return final_text

        self.conversation_history.append(
            {
                "role": "assistant",
                "content": assistant_message.content or "",
            }
        )
        return assistant_message.content or ""

    def _tool_result_text(self, result) -> str:
        if isinstance(result, list) and result:
            c = result[0]
            if hasattr(c, "text"):
                return c.text
            return str(c)
        return str(result)
