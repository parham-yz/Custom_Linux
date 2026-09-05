# Omarchy-inspired theme design

Research checked 5 September 2026. These notes guide coordinated themes for the existing Fedora/Hyprland desktop.

## What to borrow from Omarchy

Omarchy defines a shared palette, renders application templates, and applies the result across desktop components. Its Quattro documentation groups colors by purpose: background, foreground, selection, muted text, accent, and terminal colors. It also defines a neutral brightness ramp and separate surface roles. Theme folders can contain coordinated backgrounds and previews. These mechanisms make application colors agree when switching themes. [Omarchy theming documentation](https://github.com/omacom/omarchy/blob/quattro/docs/theming.md)

The legacy Omarchy 3 manual describes square corners and a shared JetBrainsMono Nerd Font. Its older theme setter refreshes Waybar, terminals, Hyprland, btop, notifications, and supported editors. Those are useful references for this desktop's existing Waybar setup; Quattro's shell configuration is a different integration target. [Omarchy 3 manual](https://learn.omacom.io/2/the-omarchy-manual), [legacy theme setter](https://raw.githubusercontent.com/omacom/omarchy/master/bin/omarchy-theme-set)

## Color and layout choices

IBM Carbon separates color roles from their values and uses neutrals for most surfaces, with additional colors assigned sparingly to actions and status. This supports one shared set of roles across several visual palettes. [Carbon color guidance](https://carbondesignsystem.com/elements/color/overview/)

For this desktop, the design recommendation is:

- Use a low-saturation neutral family for backgrounds, panels, hover states, and borders.
- Give each theme one accent family. Make the second border accent identical or a nearby shade to keep window outlines quiet.
- Keep readable text brighter than decorative borders in dark themes, and darker in light themes. Muted text must remain readable.
- Reserve red for errors and urgent states; keep ordinary status modules mostly neutral.
- Use restrained corners, consistent spacing, and subtle outlines. Preserve the compact bar and readable type size.
- Match wallpaper colors to the surfaces, with broad empty areas and limited detail. Opaque reading surfaces keep text contrast independent of wallpaper content.

These are design choices for the requested minimal appearance, not claims that one palette or geometry is objectively best.

## Readability checks

Use WCAG's sRGB contrast calculation as a practical benchmark: at least 4.5:1 for ordinary text, including secondary labels and selected text. Meaningful control indicators should reach 3:1 against adjacent colors. These thresholds do not establish complete desktop accessibility; they check specific color pairs. [W3C text contrast](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html), [W3C non-text contrast](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html)

Check foreground/background, muted/hover, accent/panel, and the foreground on a selected accent fill separately. For translucent components, evaluate the composited background. Decorative dividers can stay subtle; do not reuse a faint divider color for text or a required focus indicator.

## Candidate palette directions

These original candidates illustrate the direction; final theme names and values may differ. Ratios below were calculated locally for solid colors using the W3C formula.

| Direction | Background | Panel | Hover | Text | Muted | Accent | Text/background | Muted/hover |
|---|---|---|---|---|---|---|---:|---:|
| Sage Ink | `#171d1b` | `#202925` | `#2c3731` | `#e0e6dc` | `#a1afa3` | `#a4bea4` | 13.45 | 5.40 |
| Mist Harbor | `#192027` | `#222c35` | `#2e3c48` | `#dce4e8` | `#9eafb9` | `#99b8c7` | 12.77 | 5.00 |
| Warm Clay | `#241e1b` | `#302823` | `#3d332d` | `#eee2d5` | `#bbab9b` | `#d0ab8b` | 12.91 | 5.50 |
| Paper Sage | `#f0eee6` | `#e5e5d9` | `#d7dccd` | `#303b33` | `#566151` | `#4c6553` | 10.05 | 4.65 |

Use the background color as text on filled accent selections for these dark candidates. Paper Sage uses `#f7f6ef` on its accent fill. Their corresponding selected-text ratios are 8.53, 7.86, 7.74, and 5.89.

## Integration with this repository

The existing [`obsidian-ember` palettes](dotfiles/.config/obsidian-ember/themes) already define `BG`, `PANEL`, `HOVER`, `TEXT`, `MUTED`, `ACCENT`, `ACCENT2`, `DANGER`, `CONTRAST`, and sixteen terminal colors. Its [template directory](dotfiles/.config/obsidian-ember/theme-templates) covers Hyprland, Waybar, Kitty, Rofi, Mako, btop, and Starship. Extend these roles and the existing theme switcher to add coordinated themes.

The current Waybar template adds transparency and the Hyprland template exposes two active-border colors. Account for those settings during contrast and visual checks. Use the existing Fedora configuration and installed applications as the integration contract; Omarchy's paths and shell components are references for design.
