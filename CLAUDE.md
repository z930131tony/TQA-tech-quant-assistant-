# Claude Code — project context

## 專案規範

TQA 的規範放在 `.claude/rules/tqa.md`（防偷看、隔日開盤執行、雙軌風控、嚴禁空殼測試），每次都必須遵守：

@.claude/rules/tqa.md

## Ponytail 一律啟用

每次對話一開始就載入 ponytail skill（full 等級），不用先問。整個對話都維持啟用，除非使用者說「stop ponytail」或 `/ponytail off`。


<!-- cloude-code-toolbox:mcp-skills-awareness-begin -->

### MCP & Skills awareness (Claude Code ToolBox)

_Last synced: 2026-11-16T20:31:42.835Z._

- **Full report:** `.claude/cloude-code-toolbox-mcp-skills-awareness.md` in this workspace (auto-overwritten on each scan). Use it as ground truth for configured servers and skill folders.
- **MCP:** For **live tools** in Claude Code, enable the matching server via `/mcp`. Servers are configured in `~/.claude.json` (user) and `.mcp.json` (project).
- **When the user’s task matches a server** (e.g. Confluence work and a **Confluence** / **Atlassian** MCP is listed), **prefer that server id** and plan on tool use—not only file search.
- **Skills:** Folders below contain `SKILL.md`; attach or cite paths in chat when relevant.

#### Workspace MCP

- `c:\Users\Tony\Documents\GitHub\TQA  (tech-quant-assistant)\.mcp.json` _(workspace: TQA  (tech-quant-assistant))_ — _file missing_

_No active workspace servers in mcp.json._

#### User MCP

- `C:\Users\Tony\.claude.json` — _no servers defined_

_No active user-scoped servers in mcp.json._

#### Project skills

_None found (or no workspace open)._

#### User skills

- **hallmark** — `C:\Users\Tony\.claude\skills\hallmark` — Design skill for websites and new pages that look designed, not generated. Use when the user asks to build or design something new, or names Hallmark. Never use it on an existing design unless the user names Hallmark, as

- **ponytail** — `C:\Users\Tony\.claude\skills\ponytail` — >

- **ponytail-audit** — `C:\Users\Tony\.claude\skills\ponytail-audit` — >

- **ponytail-debt** — `C:\Users\Tony\.claude\skills\ponytail-debt` — >

- **ponytail-gain** — `C:\Users\Tony\.claude\skills\ponytail-gain` — >

- **ponytail-help** — `C:\Users\Tony\.claude\skills\ponytail-help` — >

- **ponytail-review** — `C:\Users\Tony\.claude\skills\ponytail-review` — >

<!-- cloude-code-toolbox:mcp-skills-awareness-end -->
