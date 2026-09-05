# Hermes desktop assistant

Hermes lives in the top bar. Click its icon or press **Super+Ctrl+Shift+H** to
toggle a compact native panel. Click outside or press Escape to dismiss it.
Closing the panel leaves the assistant, reminders, and notifications running.
The panel follows the current desktop palette.

## Everyday use

- **Assistant:** talk to Hermes, ask it to remember something, or schedule a
  reminder. **Meet Hermes** starts a conversational introduction, one question
  at a time, using the existing profile as context.
- **Reminders:** review scheduled work and notifications. Mark an item handled,
  snooze it until tomorrow, or pause a scheduled reminder.
- **Settings:** choose a model from the connected provider and refresh its model
  list. Discovery uses the installed Hermes provider code and existing login.
  The list refreshes when settings are opened after its six-hour cache expires;
  **Refresh list** checks immediately. If discovery is unavailable, the last
  known list remains available and is identified as saved. New selections apply
  to subsequent replies and scheduled work without restarting the gateway.
- **Alerts on / Paused:** control reminder notifications. Quiet hours are
  22:00–08:00 Europe/Berlin. Pending notifications also respect Do Not Disturb.

A small filled dot beside the bar icon means both services respond. An open dot
in the theme's warning color means Hermes is stopped or reconnecting. A separate
systemd timer checks every 30 seconds, reports failures once, and reports recovery.
It also detects an automatic restart that occurred between checks. The monitor
does not depend on the assistant's desktop server and does not call a model.
Failure notifications use the normal desktop notification system; Do Not Disturb
may delay their display. Reminder pause does not disable health monitoring.

Right-click the bar icon for controls, the optional full browser view, or the
existing coding-agent menu. The coding shortcut **Super+Ctrl+Shift+A** remains
available. The browser view can also be opened with `obsidian-hermes dashboard`.

## Accounts and memory

Email and calendar account connections are deferred. The assistant does not
currently monitor either account. Its agreed operating instructions are:

- Never send email. Follow up on messages needing a reply after 24 hours,
  including opened messages; reply, archive, or marking handled resolves the
  follow-up. Snoozing postpones it. Follow up at most once daily.
- Calendar creation and editing are allowed once connected. Deleting an event
  requires explicit confirmation of the particular event.
- Use Hermes's native memory, session history, scheduling, and approval mechanism.

These account rules must be carried into the eventual connector setup. No email
or calendar connector, broad OAuth consent flow, or automated account action is
installed here. Hermes's email and WhatsApp messaging gateways are disabled.

The existing `hermes-safe` installation is preserved. A separate native Hermes
home is seeded with its provider login, existing native memory when present, and
the approved profile. Old gateway settings, mailbox credentials, scheduled jobs,
and transcripts are not imported. Ask Hermes to review, correct, or forget a
memory; the optional full view also displays native memory files.

## Installation and operation

This integration targets the existing Fedora Asahi/Hyprland installation with
Podman, its pinned Hermes image and `hermes-firecrawl` network, Python 3 with
PyGObject/GTK 3/GtkLayerShell and PyYAML, systemd user services, and Mako. Firefox
is needed only for the optional full view. It does not install another model
runtime or replace the existing provider login.

```bash
/usr/bin/python3 scripts/install-hermes-assistant.py        # inspect
/usr/bin/python3 scripts/install-hermes-assistant.py --apply
obsidian-hermes doctor
```

The installer checks for local edits, saves overwritten files in
`~/.local/state/custom-linux-backups/hermes-assistant-*`, records installed hashes,
and enables startup. The gateway uses the existing digest-pinned ARM64 container.
It starts with the user session; overdue native cron jobs are checked when it is
running again after login or sleep. It cannot run while the machine is off.

| Component | Location |
|---|---|
| Native panel and desktop bridge | `~/.local/share/obsidian-hermes/` |
| Native Hermes state, sessions, memory, cron | `~/.local/share/obsidian-hermes/hermes/` |
| Assistant workspace and profile | `~/.local/share/obsidian-hermes/workspace/` |
| Private local API credentials | `~/.config/obsidian-hermes/` |
| Notification delivery, catalog cache, health state | `~/.local/state/obsidian-hermes/` |
| Gateway | `obsidian-hermes-gateway.service` |
| Desktop bridge | `obsidian-hermes.service` |
| Independent monitor | `obsidian-hermes-health.timer` and `.service` |

The authenticated native API is published only on `127.0.0.1:8766`; the desktop
bridge listens only on `127.0.0.1:8765`. Credentials and private runtime data are
excluded from the snapshot. The optional web view checks host, session cookie,
and origin on write requests and does not expose the gateway key to JavaScript.

Native runs continue when the panel closes. If the gateway restarts during a run,
the panel offers a retry instead of remaining busy forever. This pinned Hermes
release cannot replay lost streaming events: if an approval's details are lost
during a bridge interruption, that run is stopped and must be requested again.
An approval is never offered without its action details.

To stop background operation deliberately, stop the health timer first:

```bash
systemctl --user stop obsidian-hermes-health.timer
systemctl --user stop obsidian-hermes.service obsidian-hermes-gateway.service
```

Opening the icon starts the assistant again. Disable the units and remove the
startup line in `~/.config/hypr/hermes.conf` to keep them off across logins.

## Verification

```bash
/usr/bin/python3 scripts/test-hermes-assistant.py
# Optional, in an idle desktop session; uses fixture models and moves the pointer:
/usr/bin/python3 scripts/test-hermes-model-ui.py --live-desktop
./scripts/test-agent-integration.sh
./scripts/verify-snapshot.sh
```

Isolated tests cover notification deduplication across restart, quiet hours, Do
Not Disturb, local HTTP boundaries, model catalog caching and selection, lost-run
recovery, and health transitions. A live input regression test covers choosing a
different model with the mouse, applying it, reloading settings, and Escape. The
model popup temporarily releases the panel's exclusive keyboard grab so Hyprland
can deliver input to the menu, then restores it when the menu closes.
Desktop checks on 2026-09-05 also verified real
inside/outside clicks, Escape, repeated activation, provider inference, native
cron-to-notification delivery, live model discovery, and a controlled bridge stop
and recovery. Account monitoring remains untested because accounts are deferred.

Implementation details were checked against the installed Hermes source, with
upstream context recorded in [the research notes](hermes_assistant_research.md).
