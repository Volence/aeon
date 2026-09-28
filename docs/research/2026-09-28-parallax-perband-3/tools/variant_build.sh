#!/bin/bash
# variant_build.sh <tag> <python-edit-file> : measurement-only cdebug build of the worktree with
# an edit applied, then parallax.emp restored from the saved copy. Outputs ~/pxperf/<tag>/cdebug.*
W=/home/volence/sonic_hacks/aeon/.claude/worktrees/agent-a0dca5666d176ac8f
SP=/tmp/claude-1000/-home-volence-sonic-hacks-aeon/7c478cfc-a7ba-4825-9661-9971eb160006/scratchpad
export SIGIL_BUILD=/home/volence/sonic_hacks/sigil/target/release/sigil
export SIGIL_EMIT=/home/volence/sonic_hacks/sigil/target/release/emit_sound_blob
export TMPDIR=/home/volence/.cache/aeon-tmp
cd "$W" || exit 9
T=/home/volence/pxperf/$1; rm -rf "$T"; mkdir -p "$T"
cp engine/level/parallax.emp "$SP/parallax_saved.emp"
python3 "$2" || { cp "$SP/parallax_saved.emp" engine/level/parallax.emp; exit 4; }
cp engine/level/parallax.emp "$T/parallax.emp.variant"
FAST=1 DEBUG=1 ./build.sh > "$T/b.log" 2>&1; rc=$?
cp s4.debug.bin "$T/cdebug.bin"; cp s4.debug.lst "$T/cdebug.lst"
cp "$SP/parallax_saved.emp" engine/level/parallax.emp
cmp -s "$SP/parallax_saved.emp" engine/level/parallax.emp && echo restored || echo RESTORE-FAILED
echo "rc=$rc finished=1"
