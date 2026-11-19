anchor=top-right
layer=overlay
outer-margin=43,10,10
margin=0,0,8
width=360
height=180
padding=10
border-size=1
border-radius=0
icons=1
max-icon-size=32
font=JetBrainsMono Nerd Font 10
background-color=#{{BG}}
text-color=#{{TEXT}}
border-color=#{{BORDER}}cc
progress-color=over #{{HOVER}}
default-timeout=5000
ignore-timeout=0
max-visible=3
sort=-time

[urgency=low]
border-color=#{{MUTED}}99

[urgency=normal]
border-color=#{{BORDER}}

[urgency=critical]
border-color=#{{DANGER}}
default-timeout=0

[mode=do-not-disturb]
invisible=1

# Direct hardware feedback remains visible while ordinary alerts are silenced.
[app-name="Obsidian OSD"]
anchor=top-center
outer-margin=43,10,10
width=260
height=65
format=<b>%s</b>  %b
text-alignment=center
icons=0
history=0
default-timeout=1200
ignore-timeout=1
invisible=0
border-color=#{{BORDER}}

# Connection feedback must not cover the top-right connectivity controls.
[app-name="Network"]
anchor=bottom-left
output=eDP-1
outer-margin=12

[app-name="Bluetooth"]
anchor=bottom-left
output=eDP-1
outer-margin=12
