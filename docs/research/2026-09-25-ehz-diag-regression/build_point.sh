#!/usr/bin/env bash
# build_point.sh <label> : convert donors + build clip DEBUG in /home/volence/sonic_hacks/.aeon-ehzbis-<label>
L=$1
W=/home/volence/sonic_hacks/.aeon-ehzbis-$L
LOG=/tmp/claude-1000/-home-volence-sonic-hacks-aeon/49f49cb1-d570-40ef-a8a2-ffb2dc8e8dbc/scratchpad/bis/build_$L.log
export SIGIL_BUILD=/home/volence/sonic_hacks/sigil/target/release/sigil
export SIGIL_EMIT=/home/volence/sonic_hacks/sigil/target/release/emit_sound_blob
{
cd "$W" || { echo "finished=nocd"; exit 2; }
echo "head=$(cat .git | sed 's/gitdir: //' | xargs -I{} cat {}/HEAD) start=$(date -u +%FT%TZ) load=$(cat /proc/loadavg)"
find . -name __pycache__ -type d -prune -exec rm -rf {} +
python3 tools/s2_zone_convert.py convert s2disasm@EHZ; echo "convEHZ rc=$?"
python3 tools/s2_zone_convert.py convert s2disasm@CPZ; echo "convCPZ rc=$?"
S2CLIP=s2_ehz_cpz DEBUG=1 ./build.sh; rc=$?
echo "build rc=$rc"
if [ -f s4.s2clip.debug.bin ]; then
  python3 -c "import zlib;d=open('s4.s2clip.debug.bin','rb').read();print('crc=%08x size=%d'%(zlib.crc32(d),len(d)))"
else echo "NO BIN"; fi
echo "end=$(date -u +%FT%TZ) load=$(cat /proc/loadavg)"
echo "finished=1"
} > "$LOG" 2>&1
