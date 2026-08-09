#!/bin/bash
set -euo pipefail

# regenerate-level.sh — MANUAL re-bake of the OJZ generated level tree +
# collision tables. These outputs are COMMITTED artifacts the build consumes
# directly (see .gitignore, the level-gen parcel); the build never runs these
# generators, because they read TWO out-of-repo donor projects at paths that
# only exist on an authoring machine:
#
#   sonic_hack  (level layouts / Kosinski art / chunk+block maps) — override
#               with AEON_SONIC_HACK_DIR; default /home/volence/sonic_hacks/sonic_hack
#   skdisasm    (S&K collision shape vocabulary) — override with
#               AEON_SKDISASM_DIR; default ../skdisasm relative to this repo
#
# Run this by hand when the editor data or a donor project changes, then commit
# the regenerated tree (the level drift check — tools/verify_level_bin.py — and
# the whole-ROM byte gate confirm it). A missing donor / absent editor data is a
# HARD ERROR (ojz_strip_gen.generate() refuses the silent legacy-air fallback).
#
# USAGE (from the repo root):  tools/regenerate-level.sh

cd "$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
TOOLS="${TOOLS:-tools}"

# Build the vendored salvador (ZX0 packer) once if missing (build.sh does the
# same; re-bakes may run standalone).
if [[ ! -x "${TOOLS}/bin/salvador" ]]; then
    echo "Building salvador (ZX0 packer)..."
    make -C "${TOOLS}/salvador" -s
    mkdir -p "${TOOLS}/bin"
    cp "${TOOLS}/salvador/salvador" "${TOOLS}/bin/salvador"
fi

echo "Importing Sonic & Knuckles collision shape set (fixed 252-shape vocabulary)..."
python3 "${TOOLS}/import_sk_collision.py"

# STRESS_UNIQUIFY (P2c Task 11 stress fixture — set by build.sh's STRESS_ART path):
# inflate the act art pool to N distinct tiles via deterministic tile clones with
# re-pointed block references (see ojz_strip_gen.stress_uniquify_pool). This is a
# THROWAWAY re-bake — build.sh restores the committed tree from git afterward, so
# the uniquified pool never reaches a commit. When unset, the real pool is baked.
if [[ -n "${STRESS_UNIQUIFY:-}" ]]; then
    echo "Generating OJZ section data (STRESS uniquify N=${STRESS_UNIQUIFY})..."
    python3 "${TOOLS}/ojz_strip_gen.py" generate --stress-uniquify "${STRESS_UNIQUIFY}"
else
    echo "Generating OJZ section data..."
    python3 "${TOOLS}/ojz_strip_gen.py" generate
fi

# Editor-authored BG override (level editor art) — replaces the generated
# zone BG when games/sonic4/data/editor_bg_override.json exists.
if [[ -f games/sonic4/data/editor_bg_override.json ]]; then
    python3 "${TOOLS}/inject_editor_bg.py"
fi

# Act art pool pages → per-page ZX0/raw election (P2b manifest v2, load-time tier).
# The generator emits the globally-deduped act art pool split into fixed-size
# pages of ART_POOL_PAGE_TILES (64) tiles = 2048 B each, plus a JSON sidecar
# (ojz_act_pool_manifest.json) carrying per-page {tiles, pinned}. Here we ELECT a
# storage form per page:
#   ZX0 (form 0): [u16 BE uncompressed size][u8 flags=0][u8 version=2] wrapper +
#                 salvador (modern/V2) stream — staged decode. Kept only when it
#                 saves >= RAW_ELECT_MIN vs raw.
#   raw (form 1): the uncompressed payload, NO wrapper — DMA straight from ROM.
# The loader dispatches on the manifest form byte (not the wrapper version).
#
# Size guard: a single page must not exceed one page's VRAM bytes
# (ART_POOL_PAGE_BYTES); an oversized page is a generator bug — fail the re-bake.
ART_POOL_PAGE_BYTES=2048      # ART_POOL_PAGE_TILES (64) * 32
RAW_ELECT_NUM=9; RAW_ELECT_DEN=10   # keep .zx0 iff zx0*DEN <= raw*NUM  (>= 10% saving)
# Page count comes from the generator's manifest — pages are addressed by
# NUMERIC index (act_pool_page${k}), never by glob, so ordering is correct at
# any page count (a glob puts page10 before page2) and stale leftover pages
# from a previously larger pool are never compressed or bundled.
POOL_DIR="games/sonic4/data/generated/ojz/act1"
POOL_MANIFEST="${POOL_DIR}/ojz_act_pool_manifest.emp"
POOL_SIDECAR="${POOL_DIR}/ojz_act_pool_manifest.json"
POOL_PAGES=$(sed -n 's/^\(pub const \)\?OJZ_ACT_POOL_PAGES = \([0-9]\+\)$/\2/p' "$POOL_MANIFEST")
if [[ -z "$POOL_PAGES" ]]; then
    echo "ERROR: could not read OJZ_ACT_POOL_PAGES from ${POOL_MANIFEST}."; exit 1
fi
if [[ ! -f "$POOL_SIDECAR" ]]; then
    echo "ERROR: manifest v2 sidecar ${POOL_SIDECAR} missing (run ojz_strip_gen first)."; exit 1
fi
# Per-page {tiles, pinned} from the sidecar (one "tiles pinned" line per page).
mapfile -t PAGE_META < <(python3 -c "import json;d=json.load(open('${POOL_SIDECAR}'));[print(p['tiles'], 1 if p['pinned'] else 0) for p in d['pages']]")
if (( ${#PAGE_META[@]} != POOL_PAGES )); then
    echo "ERROR: sidecar has ${#PAGE_META[@]} pages, manifest declares ${POOL_PAGES}."; exit 1
fi
echo "Electing ZX0/raw form for ${POOL_PAGES} act art pool pages (salvador)..."
rm -f "${POOL_DIR}"/act_pool_page*.zx0 "${POOL_DIR}"/act_pool_page*.zx0.tmp "${POOL_DIR}"/act_pool_page*.raw
declare -a PAGE_FORM PAGE_EXT
for (( k = 0; k < POOL_PAGES; k++ )); do
    page_bin="${POOL_DIR}/act_pool_page${k}.bin"
    if [[ ! -f "$page_bin" ]]; then
        echo "ERROR: ${page_bin} missing but manifest declares ${POOL_PAGES} pages."; exit 1
    fi
    size=$(stat -c%s "$page_bin")
    if (( size > ART_POOL_PAGE_BYTES )); then
        echo "ERROR: ${page_bin} is ${size} B — exceeds one page (${ART_POOL_PAGE_BYTES})."; exit 1
    fi
    "${TOOLS}/bin/salvador" "$page_bin" "${page_bin%.bin}.zx0.tmp" > /dev/null
    zstream=$(stat -c%s "${page_bin%.bin}.zx0.tmp")
    zsize=$(( zstream + 4 ))          # + 4-byte wrapper
    if (( zsize * RAW_ELECT_DEN <= size * RAW_ELECT_NUM )); then
        # ZX0 wins (>= 10% saving): wrapper + stream.
        page_zx0="${page_bin%.bin}.zx0"
        printf '%b' "$(printf '\\x%02x\\x%02x\\x00\\x02' $((size >> 8)) $((size & 255)))" > "$page_zx0"
        cat "${page_bin%.bin}.zx0.tmp" >> "$page_zx0"
        PAGE_FORM[k]=0; PAGE_EXT[k]="zx0"
    else
        # raw-direct wins: the uncompressed payload, no wrapper.
        cp "$page_bin" "${page_bin%.bin}.raw"
        PAGE_FORM[k]=1; PAGE_EXT[k]="raw"
    fi
    rm -f "${page_bin%.bin}.zx0.tmp"
done

# Emit the act art pool as a native `.emp` section: page embeds followed by the
# manifest v2 table [PageManifest;N] the loader strides by page number — each
# entry {source, tiles, form, flags}. act_descriptor.emp consumes
# OJZ_Act_Pool_PageTable (Act.act_art_pool_table) across the link.
echo "Emitting act art pool .emp section (manifest v2)..."
POOL_EMP="${POOL_DIR}/ojz_act_pool.emp"
{
  echo "// AUTO-GENERATED by tools/regenerate-level.sh — DO NOT EDIT."
  echo "// OJZ Act 1 act-wide paged art pool: per-page ZX0/raw blob embeds + the"
  echo "// manifest v2 table [PageManifest;N] the loader strides by page number"
  echo "// ({source, tiles, form, flags}). Natively placed at the ojz_act_pool section;"
  echo "// consumed by act_descriptor.emp (OJZ_Act_Pool_PageTable). Pages are"
  echo "// even-length — no inter-page padding."
  echo "module games.sonic4.ojz_act_pool_act1 in ojz_act_pool"
  echo ""
  echo "use engine.structs.{PageManifest}"
  echo ""
  for (( k = 0; k < POOL_PAGES; k++ )); do
    echo "pub data OJZ_Act_Pool_Page${k} = embed(\"${POOL_DIR}/act_pool_page${k}.${PAGE_EXT[k]}\")"
  done
  echo ""
  echo "pub data OJZ_Act_Pool_PageTable: [PageManifest; ${POOL_PAGES}] = ["
  for (( k = 0; k < POOL_PAGES; k++ )); do
    tiles=${PAGE_META[k]% *}
    pinned=${PAGE_META[k]#* }
    echo "  PageManifest{ pm_source: extern(\"OJZ_Act_Pool_Page${k}\"), pm_tiles: ${tiles}, pm_form: ${PAGE_FORM[k]}, pm_flags: ${pinned} },"
  done
  echo "]"
} > "$POOL_EMP"

echo "Generating OJZ block data..."
python3 "${TOOLS}/ojz_block_gen.py" generate

# The re-bake is the ONE moment the committed tree actually changes — run the
# drift gate HERE, not just at the next build.sh. (set -euo pipefail above
# makes a verify failure abort the script with its nonzero exit.)
echo "Verifying the re-baked tree..."
python3 "${TOOLS}/verify_level_bin.py"

echo "Re-bake complete. Next: ./build.sh both shapes."
echo "The committed level tree should be byte-identical unless the editor data or"
echo "a donor project changed — review 'git status games/sonic4/data' before committing."
