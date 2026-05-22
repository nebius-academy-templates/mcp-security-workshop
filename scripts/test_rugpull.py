"""Direct integration test for the summarizer_server rug-pull behaviour.

Spawns the summarizer over stdio (exactly like Claude Code would), and walks
through the rug-pull lifecycle while printing every observable signal:

  1. Initial tools/list             -> should show BENIGN description.
  2. Call summarize(CUST-42)        -> should return placeholder; captures session.
  3. Touch summarizer_server/.rugpull.
  4. Wait for tools/list_changed    -> notification surfaces in client logs.
  5. Re-fetch tools/list            -> should show POISONED description.
  6. Call summarize(CUST-42) again  -> should now leak internal notes from the
                                       acmeops customer file (visible exfil).

Subprocess stderr (the watcher diagnostics) is streamed to this script's
stderr in real time, prefixed with `[server]`, so we can correlate what the
server reports with what the client receives.

Run with:
    uv run python scripts/test_rugpull.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

REPO_ROOT = Path(__file__).resolve().parent.parent
SENTINEL = REPO_ROOT / "summarizer_server" / ".rugpull"


def _log(msg: str) -> None:
    print(f"[test] {msg}", flush=True)


def _extract_text(content) -> str:
    parts: list[str] = []
    for c in content:
        text = getattr(c, "text", None)
        if text is not None:
            parts.append(text)
    return "\n".join(parts)


async def main() -> int:
    if SENTINEL.exists():
        _log(f"clearing pre-existing sentinel at {SENTINEL}")
        SENTINEL.unlink()

    params = StdioServerParameters(
        command="uv",
        args=["run", "python", "-m", "summarizer_server"],
        cwd=str(REPO_ROOT),
    )

    notification_event = asyncio.Event()

    async def _on_message(message: object) -> None:
        text = repr(message)
        if "ToolListChangedNotification" in text or "tools/list_changed" in text:
            _log(f"received tools/list_changed notification: {text}")
            notification_event.set()

    failures: list[str] = []

    _log("spawning summarizer_server via stdio...")
    async with stdio_client(params, errlog=sys.stderr) as (read, write):
        async with ClientSession(read, write, message_handler=_on_message) as session:
            await session.initialize()

            _log("step 1: initial tools/list")
            tools = await session.list_tools()
            for t in tools.tools:
                desc = (t.description or "").replace("\n", "\\n")
                _log(f"  tool '{t.name}' description (truncated 120ch): {desc[:120]!r}")
                if t.name == "summarize" and "IMPORTANT INTERNAL CONTEXT" in (t.description or ""):
                    failures.append("initial description already contained poisoned payload")

            _log("step 2: pre-rugpull summarize(CUST-42) — expect placeholder")
            result_before = await session.call_tool("summarize", {"customer_id": "CUST-42"})
            text_before = _extract_text(result_before.content)
            _log(f"  output: {text_before!r}")
            if "placeholder" not in text_before:
                failures.append("pre-rugpull output did not contain 'placeholder'")

            _log(f"step 3: touching sentinel at {SENTINEL}")
            SENTINEL.touch()

            _log("step 4: waiting up to 5s for tools/list_changed notification")
            try:
                await asyncio.wait_for(notification_event.wait(), timeout=5.0)
                _log("  -> notification received")
            except asyncio.TimeoutError:
                _log("  -> TIMEOUT: no notification arrived")
                failures.append("tools/list_changed notification never arrived")

            _log("step 5: re-fetching tools/list after rug pull")
            tools_after = await session.list_tools()
            for t in tools_after.tools:
                desc = (t.description or "").replace("\n", "\\n")
                _log(f"  tool '{t.name}' description (truncated 200ch): {desc[:200]!r}")
                if t.name == "summarize":
                    if "IMPORTANT INTERNAL CONTEXT" in (t.description or ""):
                        _log("  -> POISONED description detected")
                    else:
                        failures.append("post-rugpull description still benign")

            _log("step 6: post-rugpull summarize(CUST-42) — expect leaked output")
            result_after = await session.call_tool("summarize", {"customer_id": "CUST-42"})
            text_after = _extract_text(result_after.content)
            _log(f"  output: {text_after!r}")

            _log("")
            _log("=" * 72)
            _log("BEFORE vs AFTER (copy/paste-able diff for slides)")
            _log("=" * 72)
            _log(f"BEFORE: {text_before}")
            _log(f"AFTER : {text_after}")
            _log("=" * 72)

            if "Octans" not in text_after:
                failures.append("post-rugpull output did not include 'Octans' (real file not read)")
            if "Internal note" not in text_after:
                failures.append("post-rugpull output did not include 'Internal note' (leak missing)")
            if text_after == text_before:
                failures.append("post-rugpull output identical to pre-rugpull output")

    if SENTINEL.exists():
        _log(f"cleanup: removing sentinel {SENTINEL}")
        SENTINEL.unlink()

    if failures:
        _log("")
        _log("FAILED:")
        for f in failures:
            _log(f"  - {f}")
        return 1

    _log("")
    _log("ALL CHECKS PASSED: description flipped, notification fired, output mutated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
