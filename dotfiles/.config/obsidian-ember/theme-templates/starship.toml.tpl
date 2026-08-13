format = "[╭─](#{{MUTED}})$directory$git_branch$git_status$fill$cmd_duration$time\n[╰─](#{{MUTED}})$character"
add_newline = true

[directory]
style = "bold #{{ACCENT2}}"
format = "[ $path ]($style)"
truncation_length = 4
truncate_to_repo = false

[git_branch]
symbol = "git:"
style = "#{{ACCENT}}"
format = "[ $symbol$branch ]($style)"

[git_status]
style = "#{{DANGER}}"
format = "[$all_status$ahead_behind ]($style)"

[fill]
symbol = " "

[cmd_duration]
min_time = 500
style = "#{{MUTED}}"
format = "[took $duration ]($style)"

[time]
disabled = false
time_format = "%H:%M"
style = "#{{MUTED}}"
format = "[$time ]($style)"

[character]
success_symbol = "[❯](bold #{{ACCENT}})"
error_symbol = "[❯](bold #{{DANGER}})"
