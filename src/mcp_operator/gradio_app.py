"""
Operator console: Gradio UI around MCPLLMHost (tools/resources/prompts/permissions tabs).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Repo layout: packages live under `src/`. Running `python gradio_app.py` from this folder
# does not add `src` to sys.path; README uses `PYTHONPATH=src` + `python -m mcp_operator.gradio_app`.
_src_root = Path(__file__).resolve().parent.parent
if str(_src_root) not in sys.path:
    sys.path.insert(0, str(_src_root))

import os

import gradio as gr
from dotenv import load_dotenv

from agent.llm_client import llm_provider, resolved_llm_model
from agent.mcp_llm_host import MCPLLMHost
from web.branding import get_branding, read_architecture_svg
from mcp_operator.suggested_args import (
    REQUIRED_PROMPT_ARG_KEYS,
    format_prompt_list_line,
    sample_json_for_prompt,
    sample_json_for_tool,
    tool_name_from_dropdown,
)


def _mcp_error_message(exc: BaseException) -> str:
    return (
        f"MCP error ({type(exc).__name__}): {exc}\n\n"
        "· Start the MCP HTTP server first (see README).\n"
        "· Confirm MCP_SERVER_URL matches the server (default http://127.0.0.1:8000).\n"
        "· If another app uses that port, you may be talking to the wrong service."
    )


class OperatorApp(MCPLLMHost):
    """Gradio: chat + inspector + policy editor."""

    def __init__(self, server_url: str | None = None, permissions_file: str | None = None):
        super().__init__(server_url, permissions_file)
        self.tools_cache: list[str] = []
        self.prompts_cache: list[str] = []
        self._prompt_required: dict[str, list[str]] = {}

    async def gui_list_tools(self):
        try:
            await self.connect()
            self.reload_permissions()
            tools = await self.list_tools()
        except Exception as e:
            return _mcp_error_message(e), gr.update(), ""
        lines = []
        self.tools_cache = []
        for t in tools:
            self.tools_cache.append(t.name)
            perm = self.permissions.get(t.name, "ask")
            lines.append(f"- {t.name}  [{perm.upper()}]\n  {t.description or ''}\n")
        choices = [f"{n} ({self.permissions.get(n, 'ask')})" for n in self.tools_cache]
        if not choices:
            return "\n".join(lines), gr.update(choices=[]), ""
        first = self.tools_cache[0]
        sample = sample_json_for_tool(first)
        return (
            "\n".join(lines),
            gr.update(choices=choices, value=choices[0]),
            sample,
        )

    async def gui_call_tool(self, tool_selection: str, arguments_json: str, approved: bool):
        if not tool_selection:
            return "Select a tool first"
        tool_name = tool_selection.split(" (")[0]
        try:
            arguments = json.loads(arguments_json) if arguments_json.strip() else {}
        except json.JSONDecodeError as e:
            return f"Invalid JSON: {e}"
        try:
            result = await self.call_tool_with_permission(
                tool_name, arguments, approved=approved
            )
        except Exception as e:
            return _mcp_error_message(e)
        return self._tool_result_text(result)

    async def gui_list_resources(self):
        try:
            await self.connect()
            templates = await self.list_resource_templates()
        except Exception as e:
            return _mcp_error_message(e)
        out = []
        for t in templates:
            out.append(
                f"- {getattr(t, 'uriTemplate', getattr(t, 'uri', '?'))}  {getattr(t, 'name', '')}"
            )
        return "\n".join(out) if out else "(none)"

    async def gui_read_resource(self, uri: str):
        if not uri.strip():
            return "Enter a URI"
        try:
            await self.connect()
            contents = await self.read_resource(uri.strip())
        except Exception as e:
            return _mcp_error_message(e)
        if contents and len(contents) > 0:
            c = contents[0]
            return getattr(c, "text", str(c))
        return str(contents)

    async def gui_list_prompts(self):
        try:
            await self.connect()
            prompts = await self.list_prompts()
        except Exception as e:
            return _mcp_error_message(e), gr.update(choices=[], value=None), "{}"
        self.prompts_cache = [p.name for p in prompts]
        self._prompt_required = {}
        lines = []
        for p in prompts:
            req: list[str] = []
            args = getattr(p, "arguments", None) or []
            for a in args:
                if getattr(a, "required", None):
                    req.append(a.name)
            self._prompt_required[p.name] = req
            lines.append(format_prompt_list_line(p))
        if not self.prompts_cache:
            return (
                "\n".join(lines) if lines else "(none)",
                gr.update(choices=[], value=None),
                "{}",
            )
        first = self.prompts_cache[0]
        sample = sample_json_for_prompt(first)
        return (
            "\n".join(lines),
            gr.update(choices=self.prompts_cache, value=first),
            sample,
        )

    async def gui_get_prompt(self, prompt_name: str, arguments_json: str):
        if not prompt_name:
            return "Select a prompt"
        try:
            pargs = json.loads(arguments_json) if arguments_json.strip() else {}
        except json.JSONDecodeError as e:
            return f"Invalid JSON: {e}"
        required = self._prompt_required.get(prompt_name) or REQUIRED_PROMPT_ARG_KEYS.get(
            prompt_name, []
        )
        missing = [
            k
            for k in required
            if k not in pargs
            or (isinstance(pargs[k], str) and not pargs[k].strip())
        ]
        if missing:
            return (
                "Missing required argument(s): "
                + ", ".join(missing)
                + ". Edit **Arguments (JSON)** or use **List prompts** then change the "
                "dropdown to load example values."
            )
        try:
            messages = await self.get_prompt(prompt_name, pargs)
        except Exception as e:
            return _mcp_error_message(e)
        parts = []
        for msg in messages:
            role = getattr(msg, "role", "?")
            content = getattr(msg, "content", "")
            if hasattr(content, "text"):
                content = content.text
            parts.append(f"[{role}]: {content}")
        return "\n\n".join(parts)

    async def gui_configure_permission(self, tool_name: str, policy: str):
        if not tool_name:
            return "Choose a tool"
        if policy not in ("allow", "deny", "ask"):
            return "Policy must be allow, deny, or ask"
        self.permissions[tool_name] = policy
        self.save_permissions()
        self.log_audit(
            f"POLICY: {tool_name}",
            policy.upper(),
            "Operator saved permissions.json",
        )
        return f"Saved: {tool_name} = {policy}\n→ {self.permissions_file}"

    async def gui_view_audit_log(self):
        if not self.audit_log_file.exists():
            return "(empty)"
        return self.audit_log_file.read_text(encoding="utf-8")

    async def load_perm_tool_choices(self):
        try:
            tools = await self.list_tools()
        except Exception as e:
            return gr.update(choices=[], value=None), _mcp_error_message(e)
        return gr.update(choices=[t.name for t in tools]), ""

    def create_interface(self):
        async def chat_wrapper(message, hist):
            if not message.strip():
                return hist
            try:
                reply = await self.chat(message, hist)
            except Exception as e:
                reply = _mcp_error_message(e)
            return hist + [
                {"role": "user", "content": message},
                {"role": "assistant", "content": reply},
            ]

        async def reset_chat():
            self.reset_conversation()
            return []

        b = get_branding()
        _arch_block = (
            '<div style="max-width:1100px;margin:0 auto 12px">'
            + read_architecture_svg()
            + "</div>"
        )
        with gr.Blocks(
            title="Secure MCP — Admin operator",
            theme=gr.themes.Default(),
        ) as demo:
            gr.Markdown(
                f"""
# Admin operator
**MCP:** `{self.server_url}` · **HTTP** (streamable)

This console is for **operators and admins**: not just chatting with the model, but **governing** how tools are used.
Use **Permissions** to set each tool to **allow**, **ask**, or **deny** (your security posture per tool), and **Refresh audit log**
to review what was allowed, blocked, or sent for approval. **Tools / Resources / Prompts** are for **inspection** (what the server exposes).
**AI chat** exercises the same client-side policy and approval flow your users get in production—use it to validate behavior end-to-end.
"""
            )
            gr.HTML(_arch_block)
            with gr.Tabs():
                with gr.Tab("AI chat"):
                    chatbot = gr.Chatbot(label="Conversation", height=420)
                    with gr.Row():
                        msg = gr.Textbox(
                            label="Message",
                            placeholder="Ask the assistant to use workspace tools…",
                            scale=4,
                        )
                        go = gr.Button("Send", variant="primary")
                    clr = gr.Button("Clear conversation")
                    go.click(
                        chat_wrapper,
                        [msg, chatbot],
                        chatbot,
                    ).then(lambda: "", outputs=msg)
                    msg.submit(chat_wrapper, [msg, chatbot], chatbot).then(
                        lambda: "", outputs=msg
                    )
                    clr.click(reset_chat, outputs=chatbot)

                with gr.Tab("Tools"):
                    gr.Markdown(
                        "Pick a tool, then edit the JSON if needed. "
                        "Examples are filled automatically when you change the tool or click **List tools**."
                    )
                    with gr.Row():
                        with gr.Column():
                            b1 = gr.Button("List tools")
                            t1 = gr.Textbox(label="Tools", lines=12)
                        with gr.Column():
                            dd = gr.Dropdown(label="Tool", choices=[], interactive=True)
                            args = gr.Textbox(
                                label="Arguments (JSON)",
                                lines=6,
                                placeholder='{}',
                                elem_id="mcp_tools_args_json",
                            )
                            with gr.Row():
                                run = gr.Button("Call")
                                ok = gr.Button("Approve & call")
                            out = gr.Textbox(label="Result", lines=10)
                    b1.click(self.gui_list_tools, outputs=[t1, dd, args])

                    def _args_sample_for_dropdown(selection: str) -> str:
                        return sample_json_for_tool(tool_name_from_dropdown(selection))

                    dd.change(_args_sample_for_dropdown, inputs=dd, outputs=args)

                    async def _call_norm(d, a):
                        return await self.gui_call_tool(d, a, False)

                    async def _call_ok(d, a):
                        return await self.gui_call_tool(d, a, True)

                    run.click(_call_norm, [dd, args], out)
                    ok.click(_call_ok, [dd, args], out)

                with gr.Tab("Resources"):
                    with gr.Row():
                        with gr.Column():
                            lr = gr.Button("List resource templates")
                            rt = gr.Textbox(label="Templates", lines=8)
                        with gr.Column():
                            uri = gr.Textbox(
                                label="URI",
                                placeholder="file://audit/log",
                            )
                            rr = gr.Button("Read resource")
                            rc = gr.Textbox(label="Content", lines=12)
                    lr.click(self.gui_list_resources, outputs=rt)
                    rr.click(self.gui_read_resource, uri, rc)

                with gr.Tab("Prompts"):
                    gr.Markdown(
                        "Pick a prompt, then edit the JSON if needed. Examples load when you "
                        "click **List prompts** or change the **Prompt** dropdown."
                    )
                    with gr.Row():
                        with gr.Column():
                            lp = gr.Button("List prompts")
                            po = gr.Textbox(label="Prompts", lines=8)
                        with gr.Column():
                            pd = gr.Dropdown(label="Prompt", choices=[], interactive=True)
                            pa = gr.Textbox(
                                label="Arguments (JSON)",
                                lines=6,
                                placeholder='{"filename": "README.md"}',
                                elem_id="mcp_prompts_args_json",
                            )
                            gp = gr.Button("Get prompt")
                            pr = gr.Textbox(label="Rendered", lines=12)
                    lp.click(self.gui_list_prompts, outputs=[po, pd, pa])

                    def _args_sample_prompt(selection: str) -> str:
                        return sample_json_for_prompt((selection or "").strip())

                    pd.change(_args_sample_prompt, inputs=pd, outputs=pa)
                    gp.click(self.gui_get_prompt, [pd, pa], pr)

                with gr.Tab("Permissions"):
                    with gr.Row():
                        with gr.Column():
                            gr.Markdown("**Policy** (saved to the permissions file on disk)")
                            lt = gr.Button("Load tool names")
                            pdd = gr.Dropdown(label="Tool", choices=[], allow_custom_value=True)
                            pol = gr.Radio(
                                choices=["allow", "deny", "ask"],
                                label="Policy",
                                value="ask",
                            )
                            sv = gr.Button("Save", variant="primary")
                            pres = gr.Textbox(label="Status", lines=2)
                        with gr.Column():
                            gr.Markdown("**Client audit log** (operator decisions)")
                            va = gr.Button("Refresh audit log")
                            aud = gr.Textbox(label="Audit", lines=18)
                    lt.click(self.load_perm_tool_choices, outputs=[pdd, pres])
                    sv.click(self.gui_configure_permission, [pdd, pol], pres)
                    va.click(self.gui_view_audit_log, outputs=aud)

            gr.Markdown(
                f"---\n\nDesigned & built by **{b['author_name']}** · "
                f"[Source on GitHub]({b['repo_url']})"
            )

        return demo


def main():
    _repo = Path(__file__).resolve().parents[2]
    load_dotenv(_repo / ".env")
    mcp_url = os.environ.get("MCP_SERVER_URL", "http://127.0.0.1:8000")
    perm = os.environ.get("PERMISSIONS_PATH", str(_repo / "data" / "permissions.json"))
    sep = "=" * 64
    print(sep)
    print("secure-agentic-mcp | Operator (Gradio)")
    print(f"  MCP_SERVER_URL:  {mcp_url}")
    print(f"  PERMISSIONS_PATH: {perm}")
    _env_port = os.environ.get("GRADIO_SERVER_PORT", "").strip()
    if _env_port:
        print(f"  GRADIO_SERVER_PORT: {_env_port} (fixed; set empty for auto)")
    else:
        print("  GRADIO_SERVER_PORT: (unset — pick first free port from 7860 upward)")
    print(
        "  If tools list files that are missing on disk under this repo's "
        "data/workspace/, another MCP server may be using that port."
    )
    print(f"  LLM_PROVIDER: {llm_provider()}  model: {resolved_llm_model()}")
    print(sep)
    app = OperatorApp()
    # Passing None lets Gradio scan a range starting at 7860. A literal 7860 binds only that port
    # and fails if something else (e.g. another Operator instance) already uses it.
    port = int(_env_port) if _env_port else None
    host = os.environ.get("GRADIO_SERVER_NAME", "0.0.0.0")
    demo = app.create_interface()
    demo.queue().launch(server_name=host, server_port=port)


if __name__ == "__main__":
    main()
