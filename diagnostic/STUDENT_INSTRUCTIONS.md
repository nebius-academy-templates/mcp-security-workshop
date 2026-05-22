# Diagnostic — student instructions

You have **20 minutes**. Three teams have asked you to security-review their MCP servers before they ship. Each server is small (~50–100 LoC, single file). Your job: decide whether you would let each one go to production, and explain why.

## What to do

1. Read the three servers in this folder, one at a time:
   - `server-a/server.py` — the `tickets-status` server (corporate ticket-status checker)
   - `server-b/server.py` — the `log-search` server (on-call log search + diagnostics)
   - `server-c/server.py` — the `pr-helper` server (GitHub PR helper)

2. Spend **roughly 6 minutes per server**. Don't run them, just read them. Read the code, the tool descriptions, and any companion files (e.g., `server-c/tool_descriptions.yml`).

3. For each server, fill in the Miro card with **one of three verdicts** and **at least one piece of evidence**:
   - **Ship it**: the server is safe enough for production
   - **Patch first**: there are issues, list them
   - **Block**: there are issues serious enough to block release

4. **Do not look at each other's Miro cards** until time is called. We want each person's independent read.

## What to look for

This is a security review. The MCP-specific risks documented in the [MCP 2025-11-25 security best practices spec](https://modelcontextprotocol.io/specification/latest/basic/security_best_practices) and the [OWASP MCP Top 10](https://owasp.org/www-project-mcp-top-10/) are all in scope, plus classical web bugs (SQL injection, secret leaks, command injection, auth bypass).

Some servers may have zero issues. Some may have several. The point isn't to find a all of them, or even a minimum number of vulnerabilities, it's to be precise about what you do flag and why.

## Time budget

- Read servers A, B, C: 18 min (6 min each, hard timer)
- Post your verdicts: 2 min

When time is called, we'll discuss together.
