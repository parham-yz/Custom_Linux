# Desktop UI and interaction audit

Reference review and initial repository audit, 5 September 2026. Findings describe the files as inspected before the current polish pass; they are not a record of which fixes were subsequently applied.

## Omarchy reference

Omarchy Quattro presents a nested command menu with searchable entries, context-dependent visibility, and checked states. Its menu definition distinguishes hierarchy and action identifiers from displayed labels. Apply those ideas to the existing Rofi menus: consistent names, a visible route back, state-aware toggle labels, and exact action selection. [Omarchy menu documentation](https://github.com/omacom/omarchy/blob/quattro/docs/menu.md), [official menu definition](https://raw.githubusercontent.com/omacom/omarchy/quattro/default/omarchy/omarchy-menu.jsonc)

Omarchy's bar organizes launch/workspaces, time/status, and system controls into sections. Some indicators appear only when relevant. Controls open actionable panels, support keyboard access, and use predictable click/scroll actions; Escape closes panels. Its current implementation uses Quickshell. Use the interaction model as a reference for this Fedora desktop's Waybar/Rofi components. [Omarchy top-bar manual](https://raw.githubusercontent.com/omacom/omarchy/quattro/manual/05-the-top-bar.md)

## Bounded improvements

| Area | Recommended behavior |
|---|---|
| Main menu | Keep a short root list; use consistent noun labels for sections and verbs for actions. Show a breadcrumb-like prompt in submenus and append Back. |
| Back and cancel | Back returns one level. Escape closes without action. Cancel in a confirmation returns to the preceding context. Avoid automatic execution when a filter has one result. |
| Search | Use “Search actions…”, “Search networks…”, or “Search themes…” in each context. Reserve editable free text for prompts, passwords, and reminder input. |
| Toggle rows | Show current state and the resulting action, such as “Turn night light on”; refresh the menu after a toggle so the new state is visible. |
| Feedback | Show short progress messages only for operations that take time, then report the observed result. Keep errors visible and useful. Escape is not an error. |
| Bar | Reduce repeated outlines and shadows. Give the launcher, current workspace, and urgent states stronger emphasis; keep routine status neutral. Preserve the hardware notch clearance. |
| Discoverability | Put left/right/scroll actions in tooltips and keep equivalent menu or keyboard routes. Make connected, muted, and off states readable without depending on hue alone. |
| Notification and OSD | Keep ordinary notifications near the bar; use a short, replacing volume/brightness OSD with readable percentage. Do not accumulate OSD entries in notification history. |
| Capture | Show separate screenshot and recording destinations. Opening recording controls should not stop recording until Stop is selected. |

Rofi's `-no-custom` restricts selection to supplied rows while preserving cancellation. `-format i` yields a stable row index, and exit status 1 signals cancellation. Its `-mesg` supports markup, so escape dynamic names when placing them in messages. [Official Rofi dmenu manual](https://davatorium.github.io/rofi/current/rofi-dmenu.5/)

Waybar custom modules can emit text, tooltip, class, and percentage as JSON; class names support state styling. It documents `restart-interval` for continuous scripts and says it cannot be combined with `interval`. Use polling or signals deliberately. [Waybar custom-module manual](https://raw.githubusercontent.com/Alexays/Waybar/master/man/waybar-custom.5.scd)

Mako supports criteria by application and category, history control, notification actions, timeout overrides, and integer progress hints from 0 to 100. Later matching criteria override earlier values, so an OSD rule placed after Do Not Disturb can explicitly keep direct hardware feedback visible. Its documented urgency values are `low`, `normal`, and `critical`. [Mako configuration manual](https://raw.githubusercontent.com/emersion/mako/master/doc/mako.5.scd)

## Findings in the initial implementation

These are static code findings except for the explicitly noted arithmetic reproduction. Verify the current implementation after changes.

1. **Menu dispatch accepts unlisted input.** [`obsidian-menu`](dotfiles/.local/bin/obsidian-menu) uses unrestricted dmenu input and suffix/glob matching. Free text ending in a recognized action can trigger that action. Add `-no-custom`, handle cancellation, and preferably map checked row indices to stable action identifiers. Main submenus currently have no Back entry.
2. **The Utilities Wi-Fi action bypasses the custom panel.** `utilities_menu` launches `nm-connection-editor`, while the bar opens the existing [`obsidian-network`](dotfiles/.local/bin/obsidian-network) panel. Route the ordinary menu action to that panel and retain advanced settings inside it.
3. **Recording success feedback is premature.** [`obsidian-record`](dotfiles/.local/bin/obsidian-record) announces startup immediately after spawning the recorder. It clears state and announces a saved recording after waiting at most two seconds, even if the recorder still runs. Check child survival and finalization, retain state while stopping, and inspect output before claiming success. Its `menu` branch currently stops an active recording as a side effect of opening controls.
4. **Clearing reminders targets the wrong unit column.** [`obsidian-reminder`](dotfiles/.local/bin/obsidian-reminder) extracts the last `list-timers` column, which names the activated service. It then stops that service twice, leaving the timer scheduled. Enumerate timer unit names directly. The same file silently rejects invalid durations; `08` produces a Bash octal-arithmetic error, reproduced locally with `minutes=08; ((minutes > 0))`. Normalize decimal input and explain validation failures.
5. **Gap toggling changes the saved appearance.** [`obsidian-toggle`](dotfiles/.local/bin/obsidian-toggle) restores inner/outer gaps to 5/10, while [`hyprland.conf`](dotfiles/.config/hypr/hyprland.conf) specifies 4/4. Restore configured or previously observed values.
6. **Theme-dependent controls retain fixed Ember colors.** [`obsidian-capture`](dotfiles/.local/bin/obsidian-capture), recording selection, and the menu's lock action hardcode dark/amber values. Read the current palette for visual selection and lock feedback.
7. **OSD output is generic notification output.** [`obsidian-osd`](dotfiles/.local/bin/obsidian-osd) has replacement hints but no distinct application/category or short timeout. Mute displays raw `wpctl` text. Emit a dedicated identity, a human-readable state, and a short duration; style it separately in the theme template.
8. **The Mako urgency name needs correction or compatibility verification.** The initial [template](dotfiles/.config/obsidian-ember/theme-templates/mako.conf.tpl) uses `[urgency=high]`, whereas upstream documents `critical`. Use the documented value and check the installed parser. This audit did not prove that every Mako release rejects `high`.
9. **The agent bar module mixes scheduling modes.** [`waybar/config`](dotfiles/.config/waybar/config) sets both `interval` and `restart-interval`, contrary to the upstream custom-module contract. Keep its polling interval and remove the continuous-script restart option.
10. **Several ordinary states look urgent.** [`waybar/style.css`](dotfiles/.config/waybar/style.css) colors audio mute, Bluetooth off, and Wi-Fi disconnected with the danger token. Reserve danger for an actual failure or critical condition; pair normal disabled states with a changed icon and tooltip.
11. **Some menu copy describes implementation rather than the user's action.** The agent-prompt dialog discusses safe argument passing. The global [Rofi placeholder](dotfiles/.config/rofi/config.rasi) promises app/command/window search even inside fixed action menus. Give each dialog task-specific instructions.

## Verification scope

Exercise one complete menu path, Back, Escape, empty search, a toggle, and a cancelled confirmation. Use mocks for power actions and reminder cleanup. Check capture cancellation and recorder failure without claiming a file was saved. Render the main menu, one device panel, ordinary notification, and OSD in both a dark and a light theme. Check text and selected-label contrast against the actual background and preserve clear focus indication. [W3C contrast guidance](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html)
