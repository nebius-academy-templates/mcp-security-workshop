# Acme Security Brief

> The 30-second context for today's workshop. Read this once at the start; refer back as needed. Everything you need to know about the threat model is here.

## The setting

You're a senior engineer at **Acme Corp**, a B2B SaaS for retail logistics. Customers are retailers in the EU, UK, and US. ~800 employees, 3 years post-Series-C.

Your team has shipped internal MCP servers to make support engineers' lives easier. The Chief Information Security Officer (CISO) has asked engineering to do a security pass before any of these go to general production. You're responsible for the security pass.

## Compliance in scope

- **SOC 2 Type II**: The annual audit is in 4 months. Need clean logging, access reviews, secrets management.
- **GDPR**: EU customers; data residency matters; right-to-erasure has to work even when an LLM is in the middle.

## Data classification

| Tier             | Examples                                                                                                           |
| ---------------- | ------------------------------------------------------------------------------------------------------------------ |
| **Restricted**   | Auth tokens, signing keys, IdP secrets are never logged or retrievable                                             |
| **Confidential** | Customer notes, ticket bodies referencing customers, audit logs — encrypted, per-user authorization, access logged |
| **Internal**     | Aggregate metrics, internal docs                                                                                   |
| **Public**       | Marketing copy, public docs                                                                                        |

## The CISO's non-negotiables

1. **No PII exfiltration.** If an LLM ever ships customer notes off-platform, it's a breach.
2. **Per-user attribution.** "AcmeOps did this" is not an acceptable audit log entry.
3. **No long-lived shared secrets.**
4. **No confused-deputy** on any third-party API proxy.
5. **Supply-chain hygiene** on any MCP server we install.

## Acceptance criteria for production

- No checked-in secrets.
- Every tool call attributable to a real user identity within 30 seconds.
- The MCP server validates the audience claim on every inbound token.
- Per-tool least-privilege scopes (no omnibus `acme:admin`).
- A documented re-consent flow if any installed MCP server changes its tool surface.

## What's out of scope today

- Hardware HSMs, full SIEM integration, network-level egress controls.
- The frontend, the marketing site, anything that isn't an MCP server.

---

**That's the brief.** Now there are several MCP servers in front of you. Find what's broken and attempt fixes as needed.
