"""
RadioIA Agent — MCP client para operar a radio via linguagem natural.

Uso:
    python agent.py "liste os episodios de hoje"
    python agent.py                               # modo interativo
    python agent.py --model claude-haiku-4-5-20251001 "gere noticias"
"""

import asyncio
import json
import os
import sys

import anthropic
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

DEFAULT_MODEL = "claude-haiku-4-5-20251001"

SYSTEM = (
    "Você é o agente operador da RadioIA, uma rádio gerada por inteligência artificial. "
    "Você tem acesso a ferramentas para gerenciar episódios, grade de programação, "
    "fontes de conteúdo e o sistema em geral. "
    "Seja objetivo e confirme sempre o que foi feito ao final."
)


def _tool_schema(tool) -> dict:
    return {
        "name": tool.name,
        "description": tool.description or "",
        "input_schema": tool.inputSchema,
    }


def _apply_cache(tools: list[dict], system: str) -> tuple[list[dict], list[dict]]:
    """Adiciona cache_control no ultimo tool e no system prompt."""
    # Cache no último tool faz a API cachear todos os tools anteriores também
    tools_cached = [t.copy() for t in tools]
    if tools_cached:
        tools_cached[-1] = {**tools_cached[-1], "cache_control": {"type": "ephemeral"}}

    system_block = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
    return tools_cached, system_block


def _result_text(result) -> str:
    if not result.content:
        return ""
    text = "\n".join(
        c.text if hasattr(c, "text") else str(c)
        for c in result.content
    )
    if getattr(result, "isError", False):
        return f"[ERRO] {text}"
    return text


async def run(prompt: str, model: str = DEFAULT_MODEL) -> None:
    server = StdioServerParameters(
        command=sys.executable,
        args=[os.path.join(PROJECT_DIR, "mcp_server.py")],
        cwd=PROJECT_DIR,
    )

    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            mcp_tools = await session.list_tools()
            tools = [_tool_schema(t) for t in mcp_tools.tools]
            tools_cached, system_block = _apply_cache(tools, SYSTEM)
            print(f"[agent] conectado — {len(tools)} ferramentas disponíveis\n")

            messages = [{"role": "user", "content": prompt}]
            client = anthropic.Anthropic(default_headers={"anthropic-beta": "prompt-caching-2024-07-31"})

            while True:
                response = client.messages.create(
                    model=model,
                    max_tokens=4096,
                    system=system_block,
                    tools=tools_cached,
                    messages=messages,
                )

                for block in response.content:
                    if hasattr(block, "text") and block.text:
                        print(block.text)

                if response.stop_reason == "end_turn":
                    break

                tool_uses = [b for b in response.content if b.type == "tool_use"]
                if not tool_uses:
                    break

                messages.append({"role": "assistant", "content": response.content})

                tool_results = []
                for block in tool_uses:
                    args_display = json.dumps(block.input, ensure_ascii=False)
                    print(f"\n[tool] {block.name}({args_display})")
                    result = await session.call_tool(block.name, block.input)
                    content = _result_text(result)
                    preview = content[:300] + ("..." if len(content) > 300 else "")
                    print(f"[result] {preview}")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": content,
                    })

                messages.append({"role": "user", "content": tool_results})


def _parse_args() -> tuple[str, str]:
    args = sys.argv[1:]
    model = DEFAULT_MODEL

    if "--model" in args:
        idx = args.index("--model")
        if idx + 1 < len(args):
            model = args[idx + 1]
            args = args[:idx] + args[idx + 2:]

    prompt = " ".join(args).strip()
    return prompt, model


def main() -> None:
    prompt, model = _parse_args()

    if not prompt:
        print("RadioIA Agent — digite seu comando (Ctrl+C para sair)")
        print(f"modelo: {model}")
        print("-" * 50)
        try:
            prompt = input("> ").strip()
        except (KeyboardInterrupt, EOFError):
            return
        if not prompt:
            return

    asyncio.run(run(prompt, model))


if __name__ == "__main__":
    main()
