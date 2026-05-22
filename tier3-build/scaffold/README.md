# Tier 3 scaffold

This folder is your starter for the Build phase. Two tools (`echo`, `read_note`) are already wired so you don't burn time on FastMCP plumbing.

## Setup

The parent repo's `pyproject.toml` already pins `mcp[cli]`, `httpx`, `authlib`, `pyjwt[crypto]`. From the parent repo root:

```bash
uv sync
uv run python alternative-flow/acmeops-mcp-security-practice/tier3-build/scaffold/server.py
```

If you want a clean copy to hand to your partner, duplicate this folder under your name:

```bash
cp -r alternative-flow/acmeops-mcp-security-practice/tier3-build/scaffold ./mcp-build-<yourname>
```

## What to do

1. Open `../VULNERABILITY_MENU.md`. Pick **2-3** entries you'd like to seed.
2. Modify `server.py` (or add new files in your copy) so your server has those vulnerabilities.
3. Fill in `../THREAT_BRIEF_TEMPLATE.md` (copy it to `threat-brief.md` in your folder). Your partner reads this and only this when they start.
4. **Don't tell your partner what you seeded.** The brief should describe what your server *does*, not what's broken about it.
5. When time is called, swap folders with your partner.

## Then your partner attacks

Your partner uses `../ATTACK_RUNBOOK.md` to probe your server and writes their findings into `findings.md` in your folder. They get ~20 min.

## Then you patch

You get ~12 min to patch the issues your partner found. The clock matters: real-world security work is rarely "patch perfectly" — it's "patch the live exploit before lunch."

## Tips

- Don't over-engineer. The most teaching value comes from one or two **clean** bugs your partner can actually exploit.
- Keep tool descriptions short and obvious — unless tool poisoning is a vulnerability you're seeding on purpose.
- If you choose the OAuth/proxy vulns, you may want to also seed something simpler so your partner has a quick win.
- The reference parent repo has working examples of every vulnerability class in `THREATS.md` — use it if you get stuck.
