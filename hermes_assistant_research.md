# Hermes desktop assistant: implementation research

Checked 2026-09-05. These research inputs preceded implementation. The approved
design and verified installation are recorded in [HERMES_ASSISTANT.md](HERMES_ASSISTANT.md).
Account connections remain deferred.

## Version and existing installation

The official latest release API returned **v2026.8.31**, published 2026-08-31. Source checks below use that tag; the separately observed `main` revision was `2e24e06e5513fa425ccf935d2e41991cb11ff383`. Online documentation tracks development and can describe behavior newer than an installed container. [Release](https://github.com/NousResearch/hermes-agent/releases/tag/v2026.8.31)

The coordinator found an existing sandboxed Podman installation, with state under `~/.local/share/hermes-safe/data` and a digest-pinned image. Preserve that installation and its credentials. Confirm the image's own version, CLI flags, and API capabilities before choosing an integration contract; the digest was not independently mapped to this release during research.

Upstream lists Linux `aarch64` and Docker `aarch64` as Tier 1, while testing primarily Ubuntu. Fedora Asahi fits the stated glibc/systemd platform assumptions, but that is an inference, not an Asahi-specific certification. The supported fresh-install paths are the official installer or container; standalone PyPI/Homebrew installs are explicitly unsupported. [Platform support](https://hermes-agent.nousresearch.com/docs/getting-started/platform-support)

## One assistant, a persistent conversation, and a desktop home

Hermes has two distinct server surfaces. The browser dashboard starts with `hermes dashboard --no-open --host 127.0.0.1 --port 9119`; it manages configuration, sessions, and jobs, and provides a TUI-based Chat tab. It needs the `web` and `pty` extras and a built frontend. Closing its browser chat reaps the PTY; existing sessions can be resumed. `hermes serve` is the headless form of this backend. These are useful existing UIs, but do not assume they are the messaging gateway. [Dashboard](https://hermes-agent.nousresearch.com/docs/user-guide/features/web-dashboard)

For a custom desktop space, the messaging gateway's authenticated API is a more direct candidate. At release `v2026.8.31`, `gateway/platforms/api_server.py` provides:

- `POST /api/sessions` with `{ "title": "Personal assistant" }`; response has `session.id`.
- `POST /api/sessions/{id}/chat/stream` with `{ "message": "..." }`.
- SSE events `run.started`, `assistant.delta` (`delta`), `assistant.completed` (`content`), `run.completed`, `error`, and `done`; events include session/run identifiers.
- `GET /api/sessions/{id}/messages` for persisted history, and run stop/steer endpoints.
- Bearer authentication using `API_SERVER_KEY`; default port 8642; tool selection from `platform_toolsets.api_server`.

Disconnecting the session stream interrupts its live run. Implement reconnect/history recovery explicitly rather than pretending a lost stream completed. Inspect `/v1/capabilities` before depending on an endpoint. [Pinned API source](https://github.com/NousResearch/hermes-agent/blob/v2026.8.31/gateway/platforms/api_server.py)

**Design inference:** reuse one assistant gateway for chat and scheduled work. Put a small themed desktop frontend in front of its API, with Chat, Today, reminders, connection health, and memory review. Keep its gateway key server-side. Separate assistant state from the existing coding sandbox. A local data bridge can expose approved mailbox/calendar results without exposing account credentials or the whole home directory to the model.

## Automatic startup and proactive tasks

The gateway owns cron and checks due jobs every 60 seconds. Cron supports recurring and one-shot tasks, pause/resume, explicit provider/model pins, and local output under `~/.hermes/cron/output/`. It can also schedule a deterministic script without model inference. The default local delivery is a file, not a Linux notification: a desktop delivery bridge is still needed. Current docs describe per-job model pins and a guard against silently inheriting a changed global provider/model. Validate these against the installed image. [Cron](https://hermes-agent.nousresearch.com/docs/user-guide/features/cron)

Upstream recommends a user service on laptops. A user service normally starts with the user's session; lingering or a system service is needed for operation before login/after logout. For this desktop, clarify whether “when I turn on the machine” means after login or before login. Notification delivery itself requires the graphical session. Keep the existing Podman isolation and let systemd supervise the container rather than installing a second unsandboxed runtime. [Gateway lifecycle](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/)

**Design inference:** use quiet hours, notification deduplication, a snooze control, explicit failure/offline states, and one daily brief. Calendar reminders can be deterministic and need no LLM. Let the user define what “urgent email” means before permitting interruptive classification or choosing polling frequency.

## Memory and first conversation

Built-in memory stores `MEMORY.md` and `USER.md` under the active Hermes home's `memories/` directory. The documented default capacities are 2,200 and 1,375 characters. The `memory` tool curates them; snapshots are loaded into new sessions. Historical conversations are separately searchable. Upstream cautions against multiple independent agent processes writing the same Hermes home. External memory services are optional and unnecessary for a first implementation. [Persistent memory](https://hermes-agent.nousresearch.com/docs/user-guide/features/memory)

**Design inference:** first-run onboarding should be an actual conversation about preferred name/pronouns, workday, priorities, calendar and mailbox accounts, quiet hours, urgency criteria, and desired reminder style. Present the proposed durable profile for correction. Provide “What you remember”, edit, and forget controls. Avoid copying unrelated Codex memories or inferring personal facts. Keep operational policy separate from personal memories.

## Accounts: monitoring is different from replying

Do **not** use Hermes's Email gateway adapter as a passive personal inbox monitor. Its documented purpose is receiving emails addressed to the agent and replying to them; startup marks existing inbox messages seen. Mailbox inspection uses a separate integration such as the bundled Google Workspace or Himalaya skill. [Email gateway](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/email)

The bundled Google Workspace skill supports Gmail and Calendar with OAuth, preferring `gws` with a Python fallback. However, its release-pinned Python `setup.py` requests Gmail read/send/modify, Calendar write, Drive, Sheets, Docs, and contacts permissions together. It has no `--services` scope-selection argument at this tag. Do not present that script as read-only onboarding. [Pinned setup source](https://github.com/NousResearch/hermes-agent/blob/v2026.8.31/skills/productivity/google-workspace/scripts/setup.py)

Google supports `gmail.readonly` for reading messages and `calendar.events.readonly` for reading events; `calendar.calendarlist.readonly` can support selecting visible calendars. Choose the exact required scopes when creating the OAuth consent flow. Sending or modifying messages and changing events requires separate permission and product decisions. [Gmail scopes](https://developers.google.com/workspace/gmail/api/auth/scopes), [Calendar scopes](https://developers.google.com/workspace/calendar/api/auth)

No native Outlook personal-mailbox skill was established by the official Hermes catalog search. A Microsoft Graph bridge is a separate implementation option. Graph offers delegated `Mail.Read` and `Calendars.Read` for personal and work/school accounts. `Mail.ReadBasic` excludes message bodies, previews, and attachments, which limits content-based urgency assessment. Account/tenant consent remains a user step. [Microsoft permissions](https://learn.microsoft.com/en-us/graph/permissions-reference)

## Tools, providers, and consequential choices

Hermes can select explicit toolsets per platform. Be precise: the `file` set includes writes and patches; `safe` includes web, vision, and image generation, so neither name means “read-only personal assistant”. A custom allowlist plus container mounts and account scopes should enforce the desired boundary. Prompt instructions alone cannot make broadly authorized shell or account tools read-only. [Toolset definitions](https://github.com/NousResearch/hermes-agent/blob/v2026.8.31/toolsets.py)

Hermes officially documents an OpenAI Codex provider using ChatGPT device-code OAuth and an optional import of existing Codex CLI credentials. It stores its own auth state; no Codex CLI installation is required. This establishes a supported Hermes authentication path, not guaranteed entitlement or quota behavior: Hermes explicitly says plan-quota semantics are undocumented. Preserve current authentication unless the user selects a change; never display or manually copy secrets into the repo. [Provider documentation](https://hermes-agent.nousresearch.com/docs/integrations/providers/)

The design interview covered these product choices:

1. Which accounts, and whether the assistant only reads, drafts for approval, or can act autonomously.
2. Which data may be sent to the chosen model provider.
3. What deserves an immediate alert, and what belongs in a daily brief.
4. Model/provider, recurring inference budget, and monitoring cadence.
5. After-login operation versus operation before login, during sleep, or while the laptop is off.
6. Memory consent, retention, review, and forgetting behavior.
7. Whether its desktop home should be a dedicated window, a special workspace, or a compact side panel.

No account authorization, email sending, calendar mutation, credentials inspection, or live installation was performed by this research task.
