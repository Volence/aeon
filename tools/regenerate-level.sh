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
# USAGE (from the repo root):  tools/regenerate-level.sh [--no-cache]
#
# INCREMENTAL RE-BAKE (2026-08-19). The editor's edit-look-edit loop re-bakes
# after every save, and a REAL one-chunk edit used to cost 7-15 s against a
# 0.85-1.5 s no-change re-bake. MEASURED (16 cores, load ~30): the whole balloon
# was ojz_block_gen's per-section S4LZ K-sweep — 13.15 s of a 13.19 s section
# rebuild, 282 s4lz.compress calls at ~47 ms each. It was NOT the ZX0 pool
# packing (10 salvador spawns, 0.35 s total) and NOT the dedupe/spatial-order
# pass. ojz_block_gen now memoizes per (block, dictionary) as well as per
# section, so a one-chunk edit recompresses ~4 blocks instead of 282.
#
# --no-cache forces a full recompute through every cache tier (the trust escape
# hatch). The caches are PURE memoization keyed on a hash of the exact inputs
# INCLUDING the compressor source, so cached and --no-cache output are
# byte-identical by construction; see the key-completeness argument in
# tools/ojz_block_gen.py. Cache lives in tools/.cache/ (gitignored) — never in
# data/generated/, which is a committed artifact with an orphan check.

NO_CACHE=""
for arg in "$@"; do
    case "$arg" in
        --no-cache) NO_CACHE="--no-cache" ;;
    esac
done

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

# PREFLIGHT — validate EVERY precondition before the first destructive step.
#
# tools lens sweep D1 (CRITICAL): this script used to run import_sk_collision.py
# first, which unconditionally overwrites the ROM-consumed
# data/collision/{heightmaps,heightmaps_rot,angles,solidity}.bin with the base
# S&K bank — and only THEN reach ojz_strip_gen, which aborts on a missing donor
# or absent editor data. `set -euo pipefail` with no trap, so the script exited
# having already destroyed the pairing between those tables and the interned
# strip indices. The tree is normally in the interned state (data/collision/
# DIFFERS from collision/base/), so one invocation on a machine missing a donor
# left every solid surface resolving to the wrong height, angle and solidity —
# and nothing caught it: verify_level_bin.py does not look at collision at all.
#
# The preflight writes nothing. Keep it FIRST, and keep every new precondition
# in it rather than at the point of use, or this defect comes straight back.
echo "Preflight: checking donors + editor data before anything is written..."
python3 "${TOOLS}/ojz_strip_gen.py" preflight

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
#                 salvador (modern/V2) stream — staged decode. Kept only when
#                 zx0*RAW_ELECT_DEN <= raw*RAW_ELECT_NUM (>= 10% saving vs raw).
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
        # Pad to EVEN length (one trailing byte past the ZX0 end marker, never
        # read) so every successor symbol stays word-aligned. An odd blob once
        # landed OJZ_Act_Pool_PageTable at an odd address -> boot AddressError
        # (2026-08-12); sigil does not auto-align data decls and an (align: 2)
        # attr materializes a synthetic section the map contract then rejects.
        if (( $(stat -c%s "$page_zx0") % 2 == 1 )); then
            printf '\x00' >> "$page_zx0"
        fi
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
  echo "// consumed by act_descriptor.emp (OJZ_Act_Pool_PageTable). Page blobs are"
  echo "// PADDED to even length at generation (one dead byte past the ZX0 end"
  echo "// marker) — an odd blob once landed the table at an odd address -> boot"
  echo "// AddressError (2026-08-12). sigil does not auto-align data decls."
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
python3 "${TOOLS}/ojz_block_gen.py" generate ${NO_CACHE}

# The re-bake is the ONE moment the committed tree actually changes — run the
# drift gate HERE, not just at the next build.sh. (set -euo pipefail above
# makes a verify failure abort the script with its nonzero exit.)
echo "Verifying the re-baked tree..."
python3 "${TOOLS}/verify_level_bin.py"

echo "Re-bake complete. Next: ./build.sh both shapes."
echo "The committed level tree should be byte-identical unless the editor data or"
echo "a donor project changed — review 'git status games/sonic4/data' before committing."
echo
echo "COMMIT games/sonic4/data/generated/ojz/act1/DONOR_PROVENANCE.json WITH the tree."
echo "ojz_strip_gen stamped both donors' HEAD SHAs (and their dirty flags) into it as"
echo "part of this run; that stamp is the only record of which donor revisions these"
echo "bytes came from. Committing the tree without it re-opens exactly the gap it"
echo "closes. A donor reported DIRTY there means the SHA does not identify what was"
echo "read — commit the donor first if you want this bake to be reproducible."
