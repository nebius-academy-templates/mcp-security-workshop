# Threat brief — Tier 3 build phase

> Copy this file to a `threat-brief.md` filee in your scaffold folder band fill it in before your partner pulls from your repo branch. **Do not list the vulnerabilities you seeded.**

## What this server is

One paragraph. What problem does your server solve? Who would use it? What does it touch? Imagine you're handing it to a coworker for a code review.

> Example: This is a `bookmarks` MCP server for our internal team. It lets engineers ask their AI agent to save, list, and delete bookmarks of internal docs. It stores bookmarks in a local SQLite file under `./data/` and can also fetch link previews via httpx.

## Tools you exposed

List each tool by name with one line on what it does. Include any tools you renamed or added beyond `echo` and `read_note`.

| Tool            | Description                                      |
| --------------- | ------------------------------------------------ |
| `echo`          | (kept from scaffold) Echoes a string             |
| `read_note`     | (kept from scaffold) Reads a note from `./data/` |
| `<your-tool-1>` | …                                                |
| `<your-tool-2>` | …                                                |

## Auth model

How do you expect clients to authenticate? What scopes does each tool require? Be honest about what you actually implemented vs. what you wish you had.

> Example: Clients connect over stdio. The `TokenVerifier` accepts any signed JWT from `https://idp.acme.example`. Tools don't currently differentiate scopes.

## Trust assumptions

What does your server _assume_ about its environment? E.g., "tool descriptions are immutable after install," "the SQLite file is only written by us," "tokens are never reused across services," etc.

This is the most useful part of the brief. Your partner will probe whether your assumptions hold.

## What you claim is hardened

One or two things you specifically tried to get right. (No false claims here. Your partner will check your work.)

## What's intentionally out of scope

Anything you didn't build because it wasn't part of this exercise. E.g., "no rate limiting," "no audit log," "no PII handling because there's no PII in the data."

## How to run

```bash
cd <your folder>
uv run python server.py
```

Connect from Claude Code or Cursor with:

```jsonc
{
  "<your-server-name>": {
    "command": "uv",
    "args": ["run", "python", "<absolute-path>/server.py"],
  },
}
```

---

## Red-teamer: write findings here when you're done

After you swap, your partner appends their `findings.md` in this folder and commits to the repo. Don't peek until the patch phase starts.
