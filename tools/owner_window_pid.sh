#!/bin/bash
# owner_window_pid.sh — identify the process holding the owner's Oracle window
# socket, BY SOCKET PATH, never by process name.
#
# WHY THIS EXISTS. On 2026-09-05 this lane reported "the owner's window is
# closed" five or six times over a night. It was open the whole time. The check
# was `pgrep -x oracle_gui` — a binary name that does not exist in this build
# (it is oracle-frontend). A pgrep on a wrong name returns empty, which is
# indistinguishable from "not running": THE FAILURE MODE PRODUCES A CLEAN,
# CONFIDENT, WRONG NEGATIVE.
#
# Then oracle warned (2026-09-05, before the fact) that the holder may be
# renamed oracle-frontend -> oracle-player if the owner adopts the new egui
# window. Same trap, second time, and they gave us the warning early enough to
# fix it rather than rediscover it.
#
# The socket PATH is the contract. The binary name is not. Match on the path.
#
# Usage:  tools/owner_window_pid.sh [socket-path]
# Prints: "<pid> <comm>" and exits 0 if a holder exists; exits 1 if none.
set -u
SOCK="${1:-/tmp/oracle-aeon-owner.sock}"

line=$(ss -lpx 2>/dev/null | grep -F -- "$SOCK" | head -1)
if [ -z "$line" ]; then
    echo "no process is listening on $SOCK" >&2
    exit 1
fi

pid=$(printf '%s\n' "$line" | grep -oE 'pid=[0-9]+' | head -1 | cut -d= -f2)
if [ -z "$pid" ]; then
    echo "socket $SOCK is listening but ss reported no pid (permissions?)" >&2
    exit 1
fi

comm=$(cat "/proc/$pid/comm" 2>/dev/null || echo '<gone>')
echo "$pid $comm"
