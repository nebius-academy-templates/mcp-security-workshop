"""Reference implementation of the Tier 2 `tools_manifest.lock` defense.

Two subcommands:

  snapshot --command "<cmd...>" --output <path>
      Spawn an MCP server over stdio, list its tools, and write a JSON lock
      file mapping `tool_name -> sha256(name + description + canonical_schema)`.

  verify --command "<cmd...>" --lock <path>
      Spawn the server again, recompute the hashes, and diff them against the
      lock file. Prints which tools changed/were added/were removed and exits
      non-zero on any drift.

The hash inputs are deliberately the three properties the spec lets an
attacker mutate post-approval — tool name, description, and input schema — so
this catches rug-pulls that flip a tool's behavior after the user has
already trusted it.

Usage from the repo root:

    # Snapshot benign state
    rm -f summarizer_server/.rugpull
    uv run python scripts/manifest_lock.py snapshot \\
        --command "uv run python -m summarizer_server" \\
        --output summarizer_server.lock

    # Trigger rug pull
    touch summarizer_server/.rugpull

    # Verify — exits non-zero, prints the drifted hash
    uv run python scripts/manifest_lock.py verify \\
        --command "uv run python -m summarizer_server" \\
        --lock summarizer_server.lock
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import shlex
import sys
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def _canonical_schema(schema: Any) -> str:
    """Stable JSON serialisation so hashes are insensitive to key ordering."""
    if schema is None:
        return "null"
    return json.dumps(schema, sort_keys=True, separators=(",", ":"))


def _hash_tool(name: str, description: str | None, input_schema: Any) -> str:
    blob = "\n".join([
        name,
        description or "",
        _canonical_schema(input_schema),
    ])
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


async def _fetch_tool_hashes(command: list[str]) -> dict[str, dict[str, str]]:
    """Spawn the server over stdio, list tools, return name -> {hash, description}."""
    if not command:
        raise ValueError("--command must not be empty")
    params = StdioServerParameters(command=command[0], args=command[1:])
    out: dict[str, dict[str, str]] = {}
    async with stdio_client(params, errlog=sys.stderr) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            for t in tools.tools:
                input_schema = getattr(t, "inputSchema", None)
                out[t.name] = {
                    "hash": _hash_tool(t.name, t.description, input_schema),
                    "description": t.description or "",
                }
    return out


def _split_command(raw: str | None, parts: list[str] | None) -> list[str]:
    if parts:
        return parts
    if raw:
        return shlex.split(raw)
    raise SystemExit("error: --command is required")


async def _snapshot(command: list[str], output_path: Path) -> int:
    data = await _fetch_tool_hashes(command)
    lock = {
        name: {"hash": info["hash"], "description": info["description"]}
        for name, info in data.items()
    }
    output_path.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"manifest-lock: wrote {len(lock)} tool hash(es) to {output_path}", file=sys.stderr)
    for name, info in sorted(lock.items()):
        print(f"  {name}  {info['hash']}", file=sys.stderr)
    return 0


async def _verify(command: list[str], lock_path: Path) -> int:
    if not lock_path.exists():
        print(f"manifest-lock: lock file not found: {lock_path}", file=sys.stderr)
        return 2

    expected_raw = json.loads(lock_path.read_text(encoding="utf-8"))
    expected: dict[str, str] = {
        name: entry["hash"] if isinstance(entry, dict) else entry
        for name, entry in expected_raw.items()
    }

    actual = await _fetch_tool_hashes(command)

    drifted: list[str] = []
    added: list[str] = []
    removed: list[str] = []

    for name, info in actual.items():
        if name not in expected:
            added.append(name)
        elif info["hash"] != expected[name]:
            drifted.append(name)
    for name in expected:
        if name not in actual:
            removed.append(name)

    if not (drifted or added or removed):
        print(
            f"manifest-lock: OK — all {len(actual)} tool(s) match {lock_path}",
            file=sys.stderr,
        )
        return 0

    print(
        f"manifest-lock: DRIFT DETECTED against {lock_path}",
        file=sys.stderr,
    )
    for name in drifted:
        print(
            f"  CHANGED: {name}\n"
            f"    expected: {expected[name]}\n"
            f"    actual  : {actual[name]['hash']}",
            file=sys.stderr,
        )
    for name in added:
        print(f"  ADDED  : {name} ({actual[name]['hash']})", file=sys.stderr)
    for name in removed:
        print(f"  REMOVED: {name} (was {expected[name]})", file=sys.stderr)
    print(
        "manifest-lock: refusing to proceed — re-consent required before any tool call.",
        file=sys.stderr,
    )
    return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Snapshot or verify the SHA-256 hashes of an MCP server's tool descriptors.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    snap = sub.add_parser("snapshot", help="Write a lock file of tool hashes.")
    snap.add_argument("--command", help="Server launch command as one string (split with shlex).")
    snap.add_argument("--command-parts", nargs=argparse.REMAINDER, default=None,
                      help="Alternative: pass the command as remaining argv tokens.")
    snap.add_argument("--output", required=True, type=Path, help="Lock file output path.")

    ver = sub.add_parser("verify", help="Verify the running server's tools against a lock file.")
    ver.add_argument("--command", help="Server launch command as one string.")
    ver.add_argument("--command-parts", nargs=argparse.REMAINDER, default=None)
    ver.add_argument("--lock", required=True, type=Path, help="Lock file to verify against.")

    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    command = _split_command(args.command, getattr(args, "command_parts", None))

    if args.cmd == "snapshot":
        return asyncio.run(_snapshot(command, args.output))
    if args.cmd == "verify":
        return asyncio.run(_verify(command, args.lock))
    parser.error(f"unknown subcommand {args.cmd!r}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
