# Native AI agent integration

This desktop ports Omarchy 4 “Pick your coding agent” to Fedora Asahi Remix,
Hyprland, Waybar, Rofi, Kitty, and Mako. It integrates third-party coding-agent
CLIs; it does not add a model runtime to the operating system.

## What is included

- No preselected provider. Choose Claude Code, Codex, OpenCode, Pi, Oh My Pi,
  Gemini, Grok, GitHub Copilot, or Crush.
- Missing agents can be installed for the current user after a dialog shows the
  exact command and warns that the unpinned third-party installer can execute
  code. `mise` is preferred when available; npm is a fallback for listed tools.
- `Super+Shift+Ctrl+A` launches the default in a dedicated
  `org.obsidian.agent` Kitty window. `a` launches it inside the current terminal.
- `obsidian-agent prompt "Review this project"` starts with a task while keeping
  the prompt as one safe process argument.
- A self-hiding Waybar icon opens a themed Rofi usage dashboard. It shows local
  Claude/Codex/Fireworks usage, plans, available rate limits, daily totals, and
  per-model totals. Data refreshes every 15 minutes. Transcript totals are local;
  authenticated network limit checks are off until the user opts in.
- OS and crash-diagnosis skills are linked into Claude, Codex, OpenCode, and
  Gemini skill directories.
- A user service watches new systemd core-dump records. It only handles the
  logged-in user's processes. Its notification sends metadata to the selected
  agent only after the user clicks **Diagnose with AI**.

## Use

| Action | Command or control |
|---|---|
| Choose and launch | `obsidian agent pick` |
| Launch | `obsidian agent launch` or `Super+Shift+Ctrl+A` |
| Launch inline | `a` |
| Start with a task | `obsidian agent prompt "…"` |
| Usage dashboard | click the agent bar icon or `obsidian agent usage panel` |
| Refresh usage | `obsidian agent usage update --force` |
| Settings | `obsidian agent settings` |
| Diagnose a retained core | `obsidian agent crash <pid>` |
| Toggle crash watcher | OMA › AI Agents › Toggle crash diagnosis |
| Check integration | `obsidian agent doctor` |

The OMA menu also has a top-level **AI Agents** section. In Waybar, left click
opens usage, right click launches the agent, and middle click changes the shown
subscription.

## Approval and privacy

The default approval mode is **ask**. This is safer than Omarchy 4's original
unattended defaults. In **Agent Settings**, a user can explicitly choose
Omarchy-style **auto** mode. Claude then uses `--permission-mode auto`; Codex
uses `--approve-for-me`; other providers use their documented auto/yolo option.
Auto mode can let an agent modify files and run commands without another prompt.

Provider authentication remains in each provider's own files and is never copied
into this repository. Usage and cache directories are mode `0700`; records and
caches are `0600`. Local transcript summaries stay local. Network usage checks
are off by default. If explicitly enabled, Claude and Fireworks can make
authenticated usage/billing API calls and Codex can query its app-server.
Redirects are rejected, vendor API origins are fixed, and Fireworks does not
reuse OpenCode credentials unless separately opted in.

A process core is raw memory and may include passwords, tokens, prompts, private
documents, and clipboard data. Crash integration sanitizes and marks PID,
executable, signal, and time as untrusted data. It forces a read-only/plan launch
even if global auto mode is on. Full command lines and backtraces require a
second, explicit consent; raw cores are never uploaded.

## Configuration and state

- Settings: `~/.config/obsidian-agent/config.json` (`0600`)
- Usage: `~/.local/state/obsidian-agent/usage/*.json` (`0600`)
- Collector cache: `~/.cache/obsidian-agent/usage-cache`
- Skills: `~/.local/share/obsidian-agent/skills`
- Fireworks estimate: `~/.config/obsidian-agent/fireworks.json`

The configuration supports `default`, `approvalMode` (`ask` or `auto`),
`launchDirectory` (default `~/Work`), and `usageNetwork` (default `false`).
Prompts are staged through protected `0600` task files rather than exposed in
long-lived process command lines. No secrets belong in the config file.

## Provider limitations

The picker supports nine launchers, matching Omarchy 4. The usage dashboard has
collectors only for Claude, Codex, and Fireworks, also matching Omarchy. A rate
limit can be absent when a provider is signed out or has changed a private API;
local transcript totals still render. Fireworks balance is usually an estimate.

Lazy install needs network access and either `mise` or npm. Packages are not
reproducibly pinned, so the UI shows the exact command and requires consent. Oh My Pi and Crush
need `mise` or a manual install because no npm fallback is declared. Provider
login remains a separate vendor flow.

## Verification

```bash
./scripts/test-agent-integration.sh
./scripts/verify-snapshot.sh
```

After applying the snapshot, check live state:

```bash
obsidian agent doctor
systemctl --user status obsidian-agent-usage.timer
systemctl --user status obsidian-agent-crash-watch.service
```

## Research sources

The implementation was based on official Omarchy v4.0.0 material, published
2026-08-14:

- [Omarchy v4.0.0 release](https://github.com/basecamp/omarchy/releases/tag/v4.0.0)
- [AI manual](https://github.com/basecamp/omarchy/blob/v4.0.0/manual/17-ai.md)
- [Default agent selector](https://github.com/basecamp/omarchy/blob/v4.0.0/bin/omarchy-default-agent)
- [Agent launcher](https://github.com/basecamp/omarchy/blob/v4.0.0/bin/omarchy-agent)
- [Agents panel architecture](https://github.com/basecamp/omarchy/blob/v4.0.0/shell/plugins/agents/README.md)
- [Crash watcher](https://github.com/basecamp/omarchy/blob/v4.0.0/bin/omarchy-crash-watch)
- [Crash privacy skill](https://github.com/basecamp/omarchy/blob/v4.0.0/default/agents/skills/diagnose-crash/SKILL.md)
- [Post-release safer Claude/Codex modes](https://github.com/basecamp/omarchy/pull/7001)

The original panel is Quickshell/QML. This port uses Waybar for glanceable status
and Rofi for the dashboard so it remains native to this repository's existing
desktop stack.
