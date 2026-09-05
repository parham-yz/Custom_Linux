anchor=top-right
layer=overlay
outer-margin=43,10,10
margin=0,0,8
width=360
height=180
padding=14
border-size=1
border-radius=8
icons=1
max-icon-size=32
font=JetBrainsMono Nerd Font 11
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
