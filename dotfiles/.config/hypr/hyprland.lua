-- Obsidian Ember: native Hyprland 0.57 configuration.
-- Legacy hyprland.conf is retained as a recovery reference.
local home = os.getenv("HOME")
local palette = {}
for line in io.lines(home .. "/.config/obsidian-ember/current/hyprland.conf") do
  local key, color = line:match("^%s*%$(%w+)%s*=%s*(%S+)")
  if key then palette[key] = color end
end
-- Displays owns this data file, including its confirmation/rollback workflow.
for line in io.lines(home .. "/.config/hypr/obsidian-displays.conf") do
  local rule = line:match("^%s*monitor%s*=%s*(.*)")
  if rule then
    local fields = {}
    for part in (rule .. ","):gmatch("(.-),") do
      fields[#fields + 1] = part:match("^%s*(.-)%s*$")
    end
    local m = {output=fields[1], mode=fields[2], position=fields[3], scale=tonumber(fields[4]) or fields[4]}
    for i=5,#fields,2 do
      assert(fields[i] == "transform" or fields[i] == "mirror", "Unsupported Displays option")
      m[fields[i]] = tonumber(fields[i+1]) or fields[i+1]
    end
    hl.monitor(m)
  end
end

hl.config({
  ["xwayland.force_zero_scaling"] = true,
  ["input.kb_layout"] = "us",
  ["input.kb_options"] = "compose:caps",
  ["input.follow_mouse"] = 1,
  ["input.touchpad.natural_scroll"] = true,
  ["input.touchpad.tap_to_click"] = true,
  ["input.touchpad.clickfinger_behavior"] = true,
  ["input.touchpad.disable_while_typing"] = true,
  ["input.touchpad.scroll_factor"] = 0.75,
  ["input.sensitivity"] = 0,
  ["general.gaps_in"] = 4,
  ["general.gaps_out"] = 4,
  ["general.border_size"] = 2,
  ["general.col.active_border"] = {colors={palette.activeBorder1,palette.activeBorder2},angle=45},
  ["general.col.inactive_border"] = palette["inactiveBorder"],
  ["general.layout"] = "dwindle",
  ["general.resize_on_border"] = true,
  ["general.allow_tearing"] = false,
  ["decoration.rounding"] = 10,
  ["decoration.active_opacity"] = 1.0,
  ["decoration.inactive_opacity"] = 0.96,
  ["decoration.fullscreen_opacity"] = 1.0,
  ["decoration.blur.enabled"] = true,
  ["decoration.blur.size"] = 7,
  ["decoration.blur.passes"] = 3,
  ["decoration.blur.new_optimizations"] = true,
  ["decoration.blur.ignore_opacity"] = false,
  ["decoration.blur.vibrancy"] = 0.12,
  ["decoration.shadow.enabled"] = true,
  ["decoration.shadow.range"] = 24,
  ["decoration.shadow.render_power"] = 3,
  ["decoration.shadow.color"] = palette["shadowColor"],
  ["decoration.shadow.offset"] = {0,5},
  ["animations.enabled"] = true,
  ["dwindle.preserve_split"] = true,
  ["dwindle.smart_split"] = false,
  ["gestures.workspace_swipe_distance"] = 280,
  ["misc.force_default_wallpaper"] = 0,
  ["misc.disable_hyprland_logo"] = true,
  ["misc.disable_splash_rendering"] = true,
  ["misc.animate_manual_resizes"] = true,
  ["debug.vfr"] = true,
})

hl.bind("SUPER + SHIFT + CTRL + H", hl.dsp.exec_cmd("kitty --class org.hermes.agent -e /home/parham/.local/bin/hermes"), {})
hl.env("XCURSOR_SIZE", "20")
hl.env("QT_QPA_PLATFORMTHEME", "qt5ct")
hl.curve("easeOutQuint", {type="bezier",points={{0.23,1},{0.32,1}}})
hl.curve("easeInOutCubic", {type="bezier",points={{0.65,0},{0.35,1}}})
hl.animation({leaf="windows",enabled=true,speed=4,bezier="easeOutQuint",style="popin 88%"})
hl.animation({leaf="windowsOut",enabled=true,speed=3,bezier="easeInOutCubic",style="popin 88%"})
hl.animation({leaf="border",enabled=true,speed=7,bezier="default"})
hl.animation({leaf="fade",enabled=true,speed=4,bezier="easeOutQuint"})
hl.animation({leaf="workspaces",enabled=true,speed=5,bezier="easeOutQuint",style="slide"})
hl.gesture({fingers=3,direction="horizontal",action="workspace"})
hl.window_rule({match={["class"]=".*"},["suppress_event"]="maximize"})
hl.window_rule({match={["class"]="^(org.gnome.Calculator)$"},["float"]=true})
hl.window_rule({match={["class"]="^(pavucontrol)$"},["float"]=true})
hl.window_rule({match={["class"]="^(org\\.obsidian\\.agent)$"},["tile"]=true})
hl.window_rule({match={["title"]="^(Picture-in-Picture)$"},["float"]=true})
hl.window_rule({match={["title"]="^(Picture-in-Picture)$"},["pin"]=true})
hl.window_rule({match={["title"]="^(Picture-in-Picture)$"},["size"]="420 260"})
hl.layer_rule({match={["namespace"]="rofi"},["blur"]=true})
hl.layer_rule({match={["namespace"]="rofi"},["ignore_alpha"]=0})
hl.bind("SUPER + Return", hl.dsp.exec_cmd("kitty"), {})
hl.bind("SUPER + SHIFT + Return", hl.dsp.exec_cmd("firefox"), {})
hl.bind("SUPER + ALT + Return", hl.dsp.exec_cmd("kitty tmux new-session -A -s main"), {})
hl.bind("SUPER + Space", hl.dsp.exec_cmd("rofi -show drun -show-icons"), {})
hl.bind("SUPER + ALT + Space", hl.dsp.exec_cmd("~/.local/bin/obsidian-menu"), {})
hl.bind("SUPER + Escape", hl.dsp.exec_cmd("~/.local/bin/obsidian-menu system"), {})
hl.bind("SUPER + K", hl.dsp.exec_cmd("~/.local/bin/obsidian-keybindings"), {})
hl.bind("SUPER + SHIFT + F", hl.dsp.exec_cmd("dolphin"), {})
hl.bind("SUPER + SHIFT + T", hl.dsp.exec_cmd("kitty btop --force-utf --config ~/.config/btop/obsidian-ember.conf"), {})
hl.bind("SUPER + SHIFT + N", hl.dsp.exec_cmd("kitty nvim"), {})
hl.bind("SUPER + SHIFT + B", hl.dsp.exec_cmd("firefox"), {})
hl.bind("SUPER + SHIFT + ALT + B", hl.dsp.exec_cmd("firefox --private-window"), {})
hl.bind("SUPER + SHIFT + A", hl.dsp.exec_cmd("firefox --new-window https://chatgpt.com"), {})
hl.bind("SUPER + SHIFT + CTRL + A", hl.dsp.exec_cmd("~/.local/bin/obsidian-agent launch"), {})
hl.bind("SUPER + SHIFT + Y", hl.dsp.exec_cmd("firefox --new-window https://youtube.com"), {})
hl.bind("SUPER + W", hl.dsp.window.close(), {})
hl.bind("SUPER + Q", hl.dsp.window.close(), {})
hl.bind("CTRL + ALT + Delete", hl.dsp.exec_cmd("~/.local/bin/obsidian-close-all"), {})
hl.bind("SUPER + T", hl.dsp.window.float(), {})
hl.bind("SUPER + F", hl.dsp.window.fullscreen({mode="fullscreen"}), {})
hl.bind("SUPER + ALT + F", hl.dsp.window.fullscreen({mode="maximized"}), {})
hl.bind("SUPER + J", hl.dsp.layout("togglesplit"), {})
hl.bind("SUPER + P", hl.dsp.window.pseudo(), {})
hl.bind("SUPER + left", hl.dsp.focus({direction="left"}), {})
hl.bind("SUPER + right", hl.dsp.focus({direction="right"}), {})
hl.bind("SUPER + up", hl.dsp.focus({direction="up"}), {})
hl.bind("SUPER + down", hl.dsp.focus({direction="down"}), {})
hl.bind("SUPER + SHIFT + left", hl.dsp.window.swap({direction="left"}), {})
hl.bind("SUPER + SHIFT + right", hl.dsp.window.swap({direction="right"}), {})
hl.bind("SUPER + SHIFT + up", hl.dsp.window.swap({direction="up"}), {})
hl.bind("SUPER + SHIFT + down", hl.dsp.window.swap({direction="down"}), {})
hl.bind("ALT + Tab", hl.dsp.window.cycle_next({next=true}), {})
hl.bind("ALT + Tab", hl.dsp.window.bring_to_top(), {})
hl.bind("ALT + SHIFT + Tab", hl.dsp.window.cycle_next({next=false}), {})
hl.bind("ALT + SHIFT + Tab", hl.dsp.window.bring_to_top(), {})
hl.bind("SUPER + equal", hl.dsp.window.resize({x=-100,y=0,relative=true}), {})
hl.bind("SUPER + minus", hl.dsp.window.resize({x=100,y=0,relative=true}), {})
hl.bind("SUPER + SHIFT + equal", hl.dsp.window.resize({x=0,y=100,relative=true}), {})
hl.bind("SUPER + SHIFT + minus", hl.dsp.window.resize({x=0,y=-100,relative=true}), {})
hl.bind("SUPER + G", hl.dsp.group.toggle(), {})
hl.bind("SUPER + ALT + G", hl.dsp.window.move({out_of_group=true}), {})
hl.bind("SUPER + ALT + Tab", hl.dsp.group.next(), {})
hl.bind("SUPER + ALT + SHIFT + Tab", hl.dsp.group.prev(), {})
hl.bind("SUPER + mouse:272", hl.dsp.window.drag(), {mouse=true})
hl.bind("SUPER + mouse:273", hl.dsp.window.resize(), {mouse=true})
hl.bind("SUPER + 1", hl.dsp.focus({workspace="1"}), {})
hl.bind("SUPER + 2", hl.dsp.focus({workspace="2"}), {})
hl.bind("SUPER + 3", hl.dsp.focus({workspace="3"}), {})
hl.bind("SUPER + 4", hl.dsp.focus({workspace="4"}), {})
hl.bind("SUPER + 5", hl.dsp.focus({workspace="5"}), {})
hl.bind("SUPER + 6", hl.dsp.focus({workspace="6"}), {})
hl.bind("SUPER + 7", hl.dsp.focus({workspace="7"}), {})
hl.bind("SUPER + 8", hl.dsp.focus({workspace="8"}), {})
hl.bind("SUPER + 9", hl.dsp.focus({workspace="9"}), {})
hl.bind("SUPER + 0", hl.dsp.focus({workspace="10"}), {})
hl.bind("SUPER + SHIFT + 1", hl.dsp.window.move({workspace="1",follow=true}), {})
hl.bind("SUPER + SHIFT + 2", hl.dsp.window.move({workspace="2",follow=true}), {})
hl.bind("SUPER + SHIFT + 3", hl.dsp.window.move({workspace="3",follow=true}), {})
hl.bind("SUPER + SHIFT + 4", hl.dsp.window.move({workspace="4",follow=true}), {})
hl.bind("SUPER + SHIFT + 5", hl.dsp.window.move({workspace="5",follow=true}), {})
hl.bind("SUPER + SHIFT + 6", hl.dsp.window.move({workspace="6",follow=true}), {})
hl.bind("SUPER + SHIFT + 7", hl.dsp.window.move({workspace="7",follow=true}), {})
hl.bind("SUPER + SHIFT + 8", hl.dsp.window.move({workspace="8",follow=true}), {})
hl.bind("SUPER + SHIFT + 9", hl.dsp.window.move({workspace="9",follow=true}), {})
hl.bind("SUPER + SHIFT + 0", hl.dsp.window.move({workspace="10",follow=true}), {})
hl.bind("SUPER + SHIFT + ALT + 1", hl.dsp.window.move({workspace="1",follow=false}), {})
hl.bind("SUPER + SHIFT + ALT + 2", hl.dsp.window.move({workspace="2",follow=false}), {})
hl.bind("SUPER + SHIFT + ALT + 3", hl.dsp.window.move({workspace="3",follow=false}), {})
hl.bind("SUPER + SHIFT + ALT + 4", hl.dsp.window.move({workspace="4",follow=false}), {})
hl.bind("SUPER + SHIFT + ALT + 5", hl.dsp.window.move({workspace="5",follow=false}), {})
hl.bind("SUPER + SHIFT + ALT + 6", hl.dsp.window.move({workspace="6",follow=false}), {})
hl.bind("SUPER + SHIFT + ALT + 7", hl.dsp.window.move({workspace="7",follow=false}), {})
hl.bind("SUPER + SHIFT + ALT + 8", hl.dsp.window.move({workspace="8",follow=false}), {})
hl.bind("SUPER + SHIFT + ALT + 9", hl.dsp.window.move({workspace="9",follow=false}), {})
hl.bind("SUPER + SHIFT + ALT + 0", hl.dsp.window.move({workspace="10",follow=false}), {})
hl.bind("SUPER + Tab", hl.dsp.focus({workspace="e+1"}), {})
hl.bind("SUPER + SHIFT + Tab", hl.dsp.focus({workspace="e-1"}), {})
hl.bind("SUPER + CTRL + Tab", hl.dsp.focus({workspace="previous"}), {})
hl.bind("SUPER + S", hl.dsp.workspace.toggle_special("scratchpad"), {})
hl.bind("SUPER + ALT + S", hl.dsp.window.move({workspace="special:scratchpad",follow=false}), {})
hl.bind("SUPER + mouse_down", hl.dsp.focus({workspace="e+1"}), {})
hl.bind("SUPER + mouse_up", hl.dsp.focus({workspace="e-1"}), {})
hl.bind("SUPER + C", hl.dsp.exec_cmd("~/.local/bin/obsidian-clipboard copy"), {})
hl.bind("SUPER + V", hl.dsp.exec_cmd("~/.local/bin/obsidian-clipboard paste"), {})
hl.bind("SUPER + X", hl.dsp.exec_cmd("~/.local/bin/obsidian-clipboard cut"), {})
hl.bind("SUPER + CTRL + V", hl.dsp.exec_cmd("~/.local/bin/obsidian-clipboard open"), {})
hl.bind("SUPER + CTRL + E", hl.dsp.exec_cmd("~/.local/bin/obsidian-emoji"), {})
hl.bind("Print", hl.dsp.exec_cmd("~/.local/bin/obsidian-capture region"), {})
hl.bind("SUPER + SHIFT + S", hl.dsp.exec_cmd("~/.local/bin/obsidian-capture region"), {})
hl.bind("SUPER + CTRL + SHIFT + S", hl.dsp.exec_cmd("~/.local/bin/obsidian-capture screen"), {})
hl.bind("SHIFT + Print", hl.dsp.exec_cmd("~/.local/bin/obsidian-capture screen"), {})
hl.bind("ALT + Print", hl.dsp.exec_cmd("~/.local/bin/obsidian-record toggle"), {})
hl.bind("SUPER + Print", hl.dsp.exec_cmd("~/.local/bin/obsidian-capture color"), {})
hl.bind("SUPER + CTRL + Print", hl.dsp.exec_cmd("~/.local/bin/obsidian-capture ocr"), {})
hl.bind("SUPER + CTRL + C", hl.dsp.exec_cmd("~/.local/bin/obsidian-menu capture"), {})
hl.bind("SUPER + CTRL + T", hl.dsp.exec_cmd("kitty btop --force-utf --config ~/.config/btop/obsidian-ember.conf"), {})
hl.bind("SUPER + CTRL + A", hl.dsp.exec_cmd("sh -c 'command -v pavucontrol >/dev/null && exec pavucontrol || exec kitty alsamixer'"), {})
hl.bind("SUPER + CTRL + W", hl.dsp.exec_cmd("nm-connection-editor"), {})
hl.bind("SUPER + CTRL + R", hl.dsp.exec_cmd("~/.local/bin/obsidian-reminder set"), {})
hl.bind("SUPER + CTRL + ALT + R", hl.dsp.exec_cmd("~/.local/bin/obsidian-reminder show"), {})
hl.bind("SUPER + CTRL + SHIFT + R", hl.dsp.exec_cmd("~/.local/bin/obsidian-reminder clear"), {})
hl.bind("SUPER + CTRL + ALT + T", hl.dsp.exec_cmd("~/.local/bin/obsidian-notice time"), {})
hl.bind("SUPER + CTRL + ALT + B", hl.dsp.exec_cmd("~/.local/bin/obsidian-notice battery"), {})
hl.bind("SUPER + CTRL + ALT + W", hl.dsp.exec_cmd("~/.local/bin/obsidian-notice weather"), {})
hl.bind("SUPER + CTRL + Space", hl.dsp.exec_cmd("~/.local/bin/obsidian-theme wallpaper"), {})
hl.bind("SUPER + CTRL + SHIFT + Space", hl.dsp.exec_cmd("~/.local/bin/obsidian-theme switch"), {})
hl.bind("SUPER + CTRL + B", hl.dsp.exec_cmd("~/.local/bin/obsidian-toggle bar"), {})
hl.bind("SUPER + SHIFT + Space", hl.dsp.exec_cmd("~/.local/bin/obsidian-codex-fork"), {})
hl.bind("SUPER + SHIFT + Backspace", hl.dsp.exec_cmd("~/.local/bin/obsidian-toggle gaps"), {})
hl.bind("SUPER + CTRL + I", hl.dsp.exec_cmd("~/.local/bin/obsidian-toggle idle"), {})
hl.bind("SUPER + CTRL + N", hl.dsp.exec_cmd("~/.local/bin/obsidian-toggle nightlight"), {})
hl.bind("SUPER + CTRL + P", hl.dsp.exec_cmd("~/.local/bin/obsidian-power toggle"), {})
hl.bind("SUPER + comma", hl.dsp.exec_cmd("makoctl dismiss"), {})
hl.bind("SUPER + SHIFT + comma", hl.dsp.exec_cmd("makoctl dismiss --all"), {})
hl.bind("SUPER + CTRL + comma", hl.dsp.exec_cmd("~/.local/bin/obsidian-toggle notifications"), {})
hl.bind("SUPER + ALT + comma", hl.dsp.exec_cmd("makoctl invoke"), {})
hl.bind("SUPER + SHIFT + ALT + comma", hl.dsp.exec_cmd("makoctl restore"), {})
hl.bind("SUPER + slash", hl.dsp.exec_cmd("~/.local/bin/obsidian-display next"), {})
hl.bind("SUPER + ALT + slash", hl.dsp.exec_cmd("~/.local/bin/obsidian-display previous"), {})
hl.bind("XF86AudioRaiseVolume", hl.dsp.exec_cmd("~/.local/bin/obsidian-osd volume-up 5"), {repeating=true,locked=true})
hl.bind("XF86AudioLowerVolume", hl.dsp.exec_cmd("~/.local/bin/obsidian-osd volume-down 5"), {repeating=true,locked=true})
hl.bind("ALT + XF86AudioRaiseVolume", hl.dsp.exec_cmd("~/.local/bin/obsidian-osd volume-up 1"), {repeating=true,locked=true})
hl.bind("ALT + XF86AudioLowerVolume", hl.dsp.exec_cmd("~/.local/bin/obsidian-osd volume-down 1"), {repeating=true,locked=true})
hl.bind("XF86AudioMute", hl.dsp.exec_cmd("~/.local/bin/obsidian-osd volume-mute"), {locked=true})
hl.bind("XF86AudioPlay", hl.dsp.exec_cmd("playerctl play-pause"), {locked=true})
hl.bind("XF86AudioNext", hl.dsp.exec_cmd("playerctl next"), {locked=true})
hl.bind("XF86AudioPrev", hl.dsp.exec_cmd("playerctl previous"), {locked=true})
hl.bind("XF86MonBrightnessUp", hl.dsp.exec_cmd("~/.local/bin/obsidian-osd brightness-up 5"), {repeating=true,locked=true})
hl.bind("XF86MonBrightnessDown", hl.dsp.exec_cmd("~/.local/bin/obsidian-osd brightness-down 5"), {repeating=true,locked=true})
hl.bind("ALT + XF86MonBrightnessUp", hl.dsp.exec_cmd("~/.local/bin/obsidian-osd brightness-up 1"), {repeating=true,locked=true})
hl.bind("ALT + XF86MonBrightnessDown", hl.dsp.exec_cmd("~/.local/bin/obsidian-osd brightness-down 1"), {repeating=true,locked=true})
hl.bind("SHIFT + XF86MonBrightnessUp", hl.dsp.exec_cmd("~/.local/bin/obsidian-osd brightness-set 100%"), {repeating=true,locked=true})
hl.bind("SHIFT + XF86MonBrightnessDown", hl.dsp.exec_cmd("~/.local/bin/obsidian-osd brightness-set 1%"), {repeating=true,locked=true})
hl.bind("XF86KbdBrightnessUp", hl.dsp.exec_cmd("~/.local/bin/obsidian-keyboard-light up"), {repeating=true,locked=true})
hl.bind("XF86KbdBrightnessDown", hl.dsp.exec_cmd("~/.local/bin/obsidian-keyboard-light down"), {repeating=true,locked=true})
hl.bind("XF86AudioMicMute", hl.dsp.exec_cmd("echo \"start\" > ~/.config/hyprwhspr/recording_control"), {description="Speech-to-text"})
hl.bind("XF86AudioMicMute", hl.dsp.exec_cmd("echo \"stop\" > ~/.config/hyprwhspr/recording_control"), {release=true})
hl.bind("SUPER + ALT + D", hl.dsp.exec_cmd("echo \"start\" > ~/.config/hyprwhspr/recording_control"), {description="Speech-to-text"})
hl.bind("SUPER + ALT + D", hl.dsp.exec_cmd("echo \"stop\" > ~/.config/hyprwhspr/recording_control"), {release=true})
hl.window_rule({match={["class"]="^(org.obsidian.Displays|obsidian-displays)$"},["float"]=true})
hl.window_rule({match={["class"]="^(org.obsidian.Displays|obsidian-displays)$"},["center"]=true})

-- One startup owner, also callable once after migration.
hl.on("hyprland.start", function()
  hl.exec_cmd(home .. "/.local/bin/obsidian-session-start")
end)
hl.on("hyprland.shutdown", function()
  hl.exec_cmd("systemctl --user stop obsidian-hyprland-session.target")
end)
