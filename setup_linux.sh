#!/bin/bash

# This script sets up the necessery udev rules and it should be run with root privileges.
# It is needed to allow the application to access the mouse device and create a uinput device for blocking mouse input.

cat <<EOF > /etc/udev/rules.d/99-csaimbot.rules
KERNEL=="event*", SUBSYSTEM=="input", MODE="0666"
KERNEL=="uinput", SUBSYSTEM=="misc", MODE="0666", OPTIONS+="static_node=uinput"
EOF

udevadm control --reload-rules
udevadm trigger
