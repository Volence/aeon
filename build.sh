#!/bin/bash
set -euo pipefail

# THE FLIP (Spec-5 Stage 2, the point of no return): `sigil build` IS the build.
# The AS Macro Assembler (asl) + p2bin + fixheader have left the pipeline; one sigil
# invocation assembles (every .emp module lowered natively + the residual .asm DATA
# via sigil-frontend-as), links in declared order, folds the header checksum in
# emit_rom, emits the sigil-canonical .lst, and appends the deb2 symbol table via the
# surviving `convsym`. The .asm CODE twins are deleted — the .emp is the only source.
#
# APPENDIX SHAPE SPLIT (crash-report axis, owner-ruled 2026-08-04 — this SUPERSEDES the
# review-item-29 release strip): the MD Debugger island and its deb2 symbol table are
# DIAGNOSTICS, not debug EQUIPMENT. A player's crash has to be reportable, and the
# release ROM is ~9% of a 4 MB cart, so both canonical shapes this script builds —
# release and DEBUG — carry the island AND the appendix. What release still does NOT
# carry is equipment: asserts, SOUND_DEBUG_HOTKEYS, SOUND_DBG_MIRROR, boot autoplay,
# CompressionSelfTest, the sound-debug mirror.
#
# The one shape without the debugger is the opt-in LEAN profile, which is NOT reachable
# from here (it is a named off-canonical profile, like config-a/config-b):
#   sigil build --aeon . --native --lean -o lean.bin
# Lean routes every fault vector at ReleaseFault (mask, red backdrop, freeze) instead.
#
# ARTIFACT LEDGER (post-flip): the assembled anchor — the header-neutral prefix
# [0,EndOfRom) — is the PRIMARY value, and both it and the full-file CRC move on
# every golden re-freeze that changes emitted bytes. The asl-witnessed anchors
# e5765873/dab4f06c are the CONVERSION provenance, not a standing bar; deliberate
# optimization parcels have moved the anchors since. Current values live in
# sigil-harness golden/provenance.toml, not here. See golden/PROVENANCE.md and the
# native_full_rom / native_offcanonical_full gates.
#
# ---------------------------------------------------------------------------
# FAST=1 — the content-authoring loop (added 2026-08-19)
# ---------------------------------------------------------------------------
# `FAST=1 ./build.sh [game]` runs ONLY what produces the artifact and skips every
# verification lane. It exists because the editor's Build & Run loop was ~38 s, and
# the ROM itself is not what costs: MEASURED on this tree (16 cores, load ~7-9),
#
#     emp_expect_fail          22.69 s   verification  (20 real sigil builds)
#     pytest tools             12.40 s   verification
#     sigil build (the ROM)     1.15 s   ARTIFACT
#     emit_sound_blob           0.20 s   ARTIFACT
#     verify_level_bin          0.13 s   verification
#     effects_budget_check      0.09 s   verification
#     s4lint / s4budget /
#       art_rom_report /
#       gen_compression_vectors 0.04 s each
#     ----------------------------------------------------------------
#     canonical DEBUG=1 total  38.14 s   of which the assemble is 3%
#
# So NO, the assemble is not the ceiling — the two build-invoking gate lanes are
# 92% of the wall clock. FAST keeps emit_sound_blob + gen_compression_vectors (both
# EMIT ROM-consumed bytes) + the sigil build + its checksum/deb2 appendix, and drops
# s4lint, effects_budget_check, the pytest sweep, the expect-fail lane,
# verify_level_bin, art_rom_report, s4budget, the post-sigil listing gates
# (effects_seam_gate's REACHABILITY half — see below for the source half FAST now
# does run — bganim_room, sprite_tilt_gate, instashield_gate) and the ctags
# reindex. None of those write a
# byte the ROM contains, so a FAST ROM is byte-identical to the canonical ROM on
# the same tree — that identity is the contract, and skipping a lane that changed
# the artifact would be a bug in the lane.
#
# LISTING-READING GATES RUN POST-SIGIL ONLY (2026-08-26). A gate that reads a
# `.lst` must read the one THIS invocation emitted: the pre-build pytest lane used
# to re-derive the BG-animation ceiling from whatever `s4*.lst` a prior build had
# left on disk, and that listing was twice not the subject (another sigil profile's;
# then absent on a fresh tree, so a first canonical build failed its own pre-build
# lane). The pytest lane now tests the DERIVATION over a committed listing cut
# (tools/fixtures/bganim_room_excerpt.lst); the ceiling against a REAL listing is
# enforced once, below the sigil build, with a provenance check (`--built-after`:
# listing and ROM both post-date the sigil invocation — the only identity the
# listing supports, it carries no ROM name or CRC) and a fixture-freshness check
# (`--fixture`: every fixture row re-found in the fresh listing with the same
# shape). A missing listing there is a HARD failure naming the gate: sigil was asked
# for `--emit-lst`, so its absence is a build bug, not a bootstrap condition.
#
# FAST is a DEV shape: it prints a loud banner at both ends saying the lanes were
# skipped, and it is REFUSED on the STRESS_* fixture shapes, which exist to produce
# evidence. It is not a merge/ship artifact — re-run without FAST before landing.
#
# THE ONE VERIFICATION FAST DOES RUN (2026-09-02, walkthrough finding b4):
# `effects_seam_gate.py --source-only`, 14 ms, before the sigil build. Not an
# exception to the rule above so much as its correction — "skip every lane" was
# costing the author the ENTIRE run: binding a raster preset to an unwired section
# is a canonical refusal (7 test_effects_seam_gate.py failures) that FAST could not
# see at all, so the loop stayed green on a tree the real build rejects and the
# author learned it at landing. MEASURED here, 5 runs including interpreter startup:
# 0.014 s each, against a 2.07 s FAST build on the same box (load ~6.8) — under 1%.
# It checks SPELLING AND BINDING ONLY; the reachability witnesses need this build's
# listing and still run on the canonical path alone. Any further addition here must
# clear the same bar: measured, milliseconds, and it catches something that otherwise
# costs a whole authoring session.
#
# STALE LEVEL DATA (the trap FAST forced into the open — closed for BOTH paths).
# games/<game>/prebuild.sh is a documented no-op and the generated level tree is a
# COMMITTED artifact, so `./build.sh` after an editor save silently shipped the
# PREVIOUS level data; the only warning lived in tools/regenerate-level.sh's
# docstring. An Aurora session lost an hour to it on 2026-08-19. Both paths now ask
# tools/level_staleness.py (see its docstring for the compare and the exclusions):
#   canonical -> STALE is a HARD FAILURE naming tools/regenerate-level.sh
#   FAST=1    -> STALE auto-runs the re-bake, timed and reported in the banner
#
# THAT GATE HAS TWO ARMS SINCE 2026-09-02, and the second one is why the owner's
# "some seem like they're just a repeat of things" happened. mtime alone cannot see a
# DELETION — removing an editor document lowers no mtime, so the tree read fresh, the
# re-bake never ran, and the SAME build error came back byte-identical about a file
# that was gone, until someone `touch`ed something. Arm B is a committed content
# manifest of the editor sources (games/<game>/data/editor_sources.stamp.json, written
# by the re-bake); `touch` is not its escape hatch and structurally cannot become one.
#
# RE-BAKE COST (measured 2026-08-19, after the incremental re-bake parcel). The
# re-bake is part of the FAST loop whenever the editor has saved, so its cost is
# the loop's cost. On 16 cores:
#
#     no-change re-bake                 0.83 s
#     re-bake after a ONE-CHUNK edit    0.99 s   (was 14.66 s)
#     cold cache, full bake             2.82 s
#     tools/regenerate-level.sh --no-cache  10.06 s
#
# The old cliff was ojz_block_gen's per-section S4LZ K-sweep: one edited byte
# invalidated a whole section and cost 13.15 s of a 13.19 s section rebuild. It
# now memoizes per (block, dictionary) as well as per section, so an edit
# recompresses ~4 streams instead of 282. The caches are content-addressed pure
# memoization with output verification on every hit — cached and --no-cache
# output are byte-identical; see tools/ojz_block_gen.py for the key-completeness
# and integrity argument, and --no-cache for the escape hatch.

GAME="${1:-sonic4}"
# sonic4 keeps the historical ROM name s4.bin (game content); other games use their own name.
if [[ "$GAME" == "sonic4" ]]; then ROM_NAME="s4"; else ROM_NAME="$GAME"; fi
# DEBUG builds emit SUFFIXED artifacts (s4.debug.bin/.lst), so the two shapes never
# overwrite each other. ROM_NAME threads through -o/--emit-lst and s4budget below.
if [[ "${DEBUG:-0}" == "1" ]]; then ROM_NAME="${ROM_NAME}.debug"; fi

# STRESS_EVICT=1 (Art-streaming P2b Task 7 forced-eviction fixture): an off-canonical
# DEV shape — sonic4 DEBUG with the STRESS_EVICT comptime define flipped on (clamps the
# residency cache below the pool size, forcing continuous evict/reload). UNFROZEN: no
# golden, not a refreeze target — built on demand for the controller's soak. It emits a
# DISTINCT artifact (s4.stress.bin/.lst) so it never collides with the canonical shapes,
# and it fixes the whole shape (sonic4 debug), so it ignores DEBUG/GAME overrides.
if [[ "${STRESS_EVICT:-0}" == "1" ]]; then
    if [[ "$GAME" != "sonic4" ]]; then
        echo "ERROR: STRESS_EVICT=1 is a sonic4-only fixture (the OJZ act pool is the target)."
        exit 1
    fi
    ROM_NAME="s4.stress"
fi

# STRESS_ART=1 (Art-streaming P2c Task 11 stress fixture): the sonic4 DEBUG shape
# built against a UNIQUIFIED act art pool (ojz_strip_gen --stress-uniquify N,
# default 2600 tiles / >40 pages) that overwhelms the 15-frame residency cache with
# continuous evict/reload traffic. Like STRESS_EVICT it is an off-canonical DEV
# shape: UNFROZEN, no golden, a DISTINCT artifact (s4.stressart.bin/.lst), and it
# fixes the whole shape (sonic4 DEBUG), ignoring DEBUG/GAME overrides.
#
# ISOLATION — the committed real act data is NEVER overwritten. sigil places the
# act-pool .emp module by a FIXED registry PATH (not a tree walk), so a parallel
# generated dir cannot be linked without a sigil registry/path change. Instead the
# stress pool is a THROWAWAY in-place re-bake (regenerate-level.sh with
# STRESS_UNIQUIFY set) guarded by an EXIT trap that restores the generated tree +
# collision from git and cleans stress-only files (see below) — so `git status` is
# left clean of real-data changes, no sigil-side change needed.
if [[ "${STRESS_ART:-0}" == "1" ]]; then
    if [[ "$GAME" != "sonic4" ]]; then
        echo "ERROR: STRESS_ART=1 is a sonic4-only fixture (the OJZ act pool is the target)."
        exit 1
    fi
    if [[ "${STRESS_EVICT:-0}" == "1" ]]; then
        echo "ERROR: STRESS_ART and STRESS_EVICT are mutually exclusive shapes."
        exit 1
    fi
    DEBUG=1                      # the fixture needs asserts + the refcount/orphan audit
    ROM_NAME="s4.stressart"
fi
MAIN_ASM="games/${GAME}/game_root.asm"
TOOLS="${TOOLS:-tools}"

# Per-game build config (optional): may set defaults, e.g. SOUND_DRIVER_ENABLED
# (demo sets SOUND_DRIVER_ENABLED=0 — it ships no sound bank yet).
if [[ -f "games/${GAME}/build.conf" ]]; then
    source "games/${GAME}/build.conf"
fi

# Parse flags. -pe (asl print-errors-only) is now a no-op — the native build always
# streams errors — but stays accepted for CLI compatibility.
NO_LINT=0
for arg in "$@"; do
    case "$arg" in
        -nl|--no-lint) NO_LINT=1 ;;
    esac
done

# The canonical shapes (the frozen goldens) are what build.sh ships: plain + debug,
# both games. The NON-canonical sonic4 sound shapes (silent / hotkeys / mirror) are
# named off-canonical profiles now — build them directly and diff their own goldens:
#   silent sonic4          -> sigil build --native --config-b
#   debug + hotkeys+mirror -> sigil build --native --config-a
# (Building an UNPROVEN sound-toggle combo from here would ship bytes no golden gates,
# so build.sh refuses rather than emit something unverifiable. The full toggle matrix
# folds back in with the Stage-3 debug-runtime work.) demo's SOUND_DRIVER_ENABLED=0 is
# its canonical state, not an override, so this only guards sonic4.
if [[ "$GAME" == "sonic4" ]]; then
    if [[ "${SOUND_DRIVER_ENABLED:-1}" != "1" \
       || "${SOUND_DEBUG_HOTKEYS:-0}" == "1" \
       || "${SOUND_DBG_MIRROR:-0}" == "1" ]]; then
        echo "ERROR: non-canonical sonic4 sound shapes are the off-canonical profiles now:"
        echo "  silent sonic4          -> sigil build --native --config-b -o s4.bin"
        echo "  debug + hotkeys+mirror -> sigil build --native --config-a -o s4.debug.bin"
        exit 1
    fi
fi

# CRASH_REPORT is not an env axis of this script: the two shapes build.sh ships (release
# and DEBUG) both carry the MD Debugger island + deb2 symbols, by the 2026-08-04 ruling.
# The debugger-less shape is the named LEAN profile, gated by its own goldens — same
# treatment as the non-canonical sound shapes above.
if [[ "${CRASH_REPORT:-1}" != "1" ]]; then
    echo "ERROR: CRASH_REPORT=0 is not a build.sh shape — it is the off-canonical lean profile:"
    echo "  no debugger, no deb2 symbols -> sigil build --aeon . --native --lean -o lean.bin"
    exit 1
fi

# FAST=1 — artifact-only build for the content-authoring loop (see the header block).
# It changes NO bytes; it only decides which lanes run. Refused on the STRESS_* fixture
# shapes: those are built to PRODUCE EVIDENCE (a soak, a stress ROM someone reasons
# about), which is the one thing an unverified build must not be used for. build.sh has
# no other landing-flow context — it does not know about merges or freezes — so for
# every other misuse the banner is the guard, by design rather than by omission.
FAST="${FAST:-0}"
if [[ "$FAST" == "1" ]]; then
    if [[ "${STRESS_EVICT:-0}" == "1" || "${STRESS_ART:-0}" == "1" ]]; then
        echo "ERROR: FAST=1 is refused on the STRESS_* fixture shapes."
        echo "  Those shapes exist to produce EVIDENCE (soaks, stress ROMs read as results),"
        echo "  and FAST skips every verification lane. Build them canonically."
        exit 1
    fi
    if [[ "${CONTRACTS:-1}" == "0" ]]; then
        echo "ERROR: FAST=1 with CONTRACTS=0 leaves the build checked by nothing at all."
        echo "  CONTRACTS=0 is the emergency opt-out for a broken contract checker; pair it"
        echo "  with a canonical build so something is still gating."
        exit 1
    fi
    echo "================================================================================"
    echo " FAST BUILD — VERIFICATION LANES SKIPPED. NOT a merge/ship artifact."
    echo "   skipped: s4lint · effects_budget_check · pytest tools · emp_expect_fail"
    echo "            verify_level_bin · art_rom_report · s4budget · bganim_room (the"
    echo "            BG-anim ceiling is NOT checked) · sprite_tilt_gate (the tilt is NOT"
    echo "            executed) · instashield_gate (NEITHER the insta-shield NOR the"
    echo "            Tails-flight precondition is executed) · loop_crossover_gate (the"
    echo "            crossover read site is NOT executed) · ctags · effects_seam_gate's"
    echo "            REACHABILITY half (its witnesses need this build's listing — see below)"
    echo "   run:     emit_sound_blob · gen_compression_vectors · sigil build (+checksum,"
    echo "            +deb2 symbols) · level re-bake IF STALE · effects_seam_gate"
    if [[ "${GAME}" == "sonic4" ]]; then
    echo "            --source-only (seam spelling + raster binding, 14 ms)"
    fi
    echo "   Re-run without FAST=1 before you land, merge, freeze, or quote a number."
    echo "================================================================================"
    # One switch for the whole source-gate block below; the ctags/budget/level lanes
    # carry their own FAST guards at their sites.
    NO_LINT=1
fi

# The sigil build binary — THE assembler now. No asl fallback: a missing/failed sigil
# is a HARD ERROR (mirrors the seam-1 SIGIL_EMIT dependency).
SIGIL_BUILD="${SIGIL_BUILD:-}"
if [[ -z "${SIGIL_BUILD}" || ! -x "${SIGIL_BUILD}" ]]; then
    echo "ERROR: build.sh needs the sigil build binary — set SIGIL_BUILD to it."
    echo "  (sigil build IS the build now; asl has left the pipeline. Build the sigil"
    echo "   toolchain first: cargo build --release --bin sigil.)"
    exit 1
fi

# --- ASSEMBLER PROVENANCE (consumer half of sigil's --version witness, 9c08f2a5) ---
# WHY THIS EXISTS AND WHY A CRC CANNOT REPLACE IT: a stale assembler and a current one
# emit byte-identical ROMs whenever the SOURCE has not changed, so every artifact check
# we have is silent on which binary produced it. The incident: the shared
# target/release/sigil sat three days behind while aeon builds invoked it, and nothing
# in the pipeline was capable of noticing. sigil now reports its own identity; asking is
# aeon's half, and this is where the failure actually bit.
#
# POSTURE: warn loudly, do not refuse — with SIGIL_VERSION_STRICT=1 to make it fatal.
# A hard default error would break every build in the workspace the moment anyone
# rebuilds sigil, and deliberately assembling with an older binary is a legitimate
# bisect move. But the warning is a BANNER, not a log line: an easy-to-miss warning
# about an easy-to-miss failure is not a control.
SIGIL_VERSION_RAW="$("${SIGIL_BUILD}" --version 2>/dev/null || true)"
if [[ -z "${SIGIL_VERSION_RAW}" ]]; then
    echo "NOTE: ${SIGIL_BUILD} does not support --version; assembler provenance unavailable."
    echo "      (Expected on a binary built before sigil 9c08f2a5. Rebuild to get it.)"
    SIGIL_REV="unknown"
else
    SIGIL_REV="$(sed -n 's/^ *revision: *//p'  <<<"${SIGIL_VERSION_RAW}" | head -1)"
    SIGIL_SRC="$(sed -n 's/^ *source: *//p'    <<<"${SIGIL_VERSION_RAW}" | head -1)"
    SIGIL_TREE="$(sed -n 's/^ *tree: *//p'     <<<"${SIGIL_VERSION_RAW}" | head -1)"
    echo "Assembler: sigil ${SIGIL_REV:0:12} (${SIGIL_TREE:-tree state unreported})"

    _sigil_stale=""
    # Currency check against the source dir the BINARY names — the right revision to
    # read here, because the question is "was this binary built from that tree's
    # current state", which only the tip can answer. (Contrast the recovery direction,
    # where a pin is correct; see docs/OVERSEER.md.)
    # FAIL CLOSED ON ALL THREE COUNTS (2026-08-27). Every arm below used to fall
    # through silently, so "I could not tell" and "it is fine" produced the same
    # exit code — and SIGIL_VERSION_STRICT=1 passed having compared nothing.
    #
    #   (1) `-d "${SIGIL_SRC}/.git"` is FALSE in a linked git worktree, where .git
    #       is a FILE ("gitdir: ...") and not a directory. Found by the sigil lane,
    #       reproduced here. That skipped the whole revision check in exactly the
    #       configuration our own OVERSEER.md prescribes for reference and landing
    #       runs, i.e. the runs where you most want this alarm armed.
    #       `rev-parse --git-dir` resolves in both layouts, so ask git, not the
    #       filesystem.
    #   (2) An unresolvable/absent SIGIL_SRC, or an unreadable HEAD, is now the
    #       distinct state `unknown` rather than silence.
    #   (3) The tree-state word is matched POSITIVELY against the known-clean
    #       spelling; ANY other word — including one sigil has not invented yet —
    #       reads as dirty. The old `== dirty*` prefix test silently went quiet on
    #       any third state word (sigil's pending `clean-sources` is the first, and
    #       would have been the first of many).
    if [[ -z "${SIGIL_SRC}" ]]; then
        _sigil_stale="unknown"
    elif ! git -C "${SIGIL_SRC}" rev-parse --git-dir >/dev/null 2>&1; then
        _sigil_stale="unknown"
    else
        _src_head="$(git -C "${SIGIL_SRC}" rev-parse HEAD 2>/dev/null || true)"
        if [[ -z "${_src_head}" || -z "${SIGIL_REV}" ]]; then
            _sigil_stale="unknown"
        elif [[ "${_src_head}" != "${SIGIL_REV}" ]]; then
            _sigil_stale="revision"
        fi
    fi
    # Positive match on the known-clean words; anything unrecognised is treated as dirty.
    # Vocabulary is exactly {clean, clean-sources, dirty, unknown}, read from sigil's source
    # (crates/sigil-cli/src/tree_class.rs state_and_detail, asserted in
    # crates/sigil-cli/tests/version_provenance.rs:823) at sigil d5967f87, 2026-08-30.
    # `clean-sources` = uncommitted changes exist but NONE in the sources this binary is compiled
    # from, so the binary DOES match its source and warning here is a false alarm. It was one:
    # `clean-sources` has a hyphen, missed the old `clean\ *` arm, and hit the catch-all.
    # Their doc USED to tell consumers to key on the `dirty` PREFIX. We declined: that fails OPEN,
    # because any word the vocabulary does not yet contain — a new state, a typo, an empty capture —
    # does not begin `dirty` and so reads as trustworthy. A positive match on the trusted words
    # fails CLOSED. The sigil lane agreed and amended their source (sigil `1c7fe7f9`, on their
    # origin/master, verified here): the advice is reversed at the definition, and the division is
    # written in beside the vocabulary — "the vocabulary is this function's to define; the
    # fail-safe direction is the consumer's to keep, and a consumer enumerating the trusted words
    # MUST BE TOLD WHEN A WORD IS ADDED."
    # SO THIS ARM HAS A LIVE CROSS-REPO COUPLING, and it fails in the loud direction: if sigil adds
    # a fifth state word and we are not told, this build starts warning (and under
    # SIGIL_VERSION_STRICT=1, REFUSING) on a tree that is fine. That is the trade taken knowingly —
    # noisy beats silent for a check no CRC, pin or golden downstream can back up. If that warning
    # ever appears with an unfamiliar word in it, the fix is to add the arm, not to remove the check.
    case "${SIGIL_TREE}" in
        clean|clean\ *|clean-sources|clean-sources\ *) ;;
        *) _sigil_stale="${_sigil_stale:+${_sigil_stale}+}dirty" ;;
    esac

    if [[ -n "${_sigil_stale}" ]]; then
        echo "############################################################################"
        echo "## WARNING: THE ASSEMBLER MAY NOT MATCH ITS SOURCE (${_sigil_stale})"
        echo "##"
        [[ "${_sigil_stale}" == *revision* ]] && {
        echo "##   binary built from : ${SIGIL_REV}"
        echo "##   ${SIGIL_SRC} HEAD : ${_src_head}"; }
        [[ "${_sigil_stale}" == *dirty* ]] && \
        echo "##   tree at capture   : ${SIGIL_TREE}"
        [[ "${_sigil_stale}" == *unknown* ]] && {
        echo "##   COULD NOT CHECK the assembler against its source."
        echo "##   source dir        : ${SIGIL_SRC:-<not reported by the binary>}"
        echo "##   This is NOT a clean bill of health. It is reported because a check"
        echo "##   that cannot run must never be indistinguishable from one that passed."; }
        echo "##"
        echo "##   A stale assembler emits a byte-IDENTICAL ROM whenever the source has"
        echo "##   not changed, so no CRC, pin or golden downstream of here can detect"
        echo "##   this. That is the whole reason it is checked at invocation."
        echo "##   Rebuild:  cargo build --release --manifest-path ${SIGIL_SRC}/Cargo.toml"
        echo "##   Set SIGIL_VERSION_STRICT=1 to make this fatal."
        echo "############################################################################"
        if [[ "${SIGIL_VERSION_STRICT:-0}" == "1" ]]; then
            echo "ERROR: SIGIL_VERSION_STRICT=1 and the assembler is ${_sigil_stale}."
            exit 1
        fi
    fi
fi
export SIGIL_REV

# The resident sound blob + banked sound data are sigil-native-linked (seam-1/seam-2);
# this preflight regenerates engine/sound/generated (the .bin blobs the sound-bank .emp
# sections embed(), including the three-way-split MT bank) from the .emp sources.
# Sound-ON games only (demo is silent).
if [[ "${SOUND_DRIVER_ENABLED:-1}" == "1" ]]; then
    SIGIL_EMIT="${SIGIL_EMIT:-}"
    if [[ -z "${SIGIL_EMIT}" || ! -x "${SIGIL_EMIT}" ]]; then
        echo "ERROR: seam-1 needs the sigil emit_sound_blob binary — set SIGIL_EMIT to it."
        exit 1
    fi
    echo "Emitting the native-linked resident sound blob (sigil)..."
    mkdir -p engine/sound/generated
    if ! "${SIGIL_EMIT}" --aeon . --out-dir engine/sound/generated; then
        echo "ERROR: sigil emit_sound_blob failed — cannot build the resident sound blob."
        exit 1
    fi
fi

# Build the vendored salvador (ZX0 packer) once if missing
if [[ ! -x "${TOOLS}/bin/salvador" ]]; then
    echo "Building salvador (ZX0 packer)..."
    make -C "${TOOLS}/salvador" -s
    mkdir -p "${TOOLS}/bin"
    cp "${TOOLS}/salvador/salvador" "${TOOLS}/bin/salvador"
fi

# Announce the suite root and the empyrean checkout, and the step that produced each
# (empyrean contract/SUITE_PATHS.md: "say which step answered" before working against
# the path). On BOTH paths, because the FAST re-bake resolves its donors through the
# same resolver; ~30 ms. A set-but-wrong EMPYREAN_SUITE_ROOT / EMPYREAN_DIR is one
# named line on stderr and exit 1, which `set -e` makes build-fatal HERE, not deeper.
echo "Resolving suite paths..." && python3 "${TOOLS}/suite_paths.py"

# ---------------------------------------------------------------------------
# LEVEL-DATA STALENESS GATE  (closes the silent-stale-data trap, 2026-08-19)
# ---------------------------------------------------------------------------
# games/<game>/prebuild.sh is a no-op and the generated level tree is a COMMITTED
# artifact (its generators need out-of-repo donors), so nothing here ever noticed
# that the editor had saved since the last re-bake. Save -> build -> reload shipped
# the PREVIOUS level data, silently, and the only warning in the tree was a docstring
# in tools/regenerate-level.sh. An Aurora editing session lost an hour to it.
#
# tools/level_staleness.py owns the compare (whole-tree newest-mtime, whole-second
# granularity) and the exclusion list — read its docstring before changing either;
# in particular the exclusions are enumerated there with a reason each, and the
# reason a per-file pair map is deliberately NOT maintained is there too.
#
# exit 0 = fresh/not-applicable, 2 = stale, 1 = the tool itself broke (which fails
# the build in both modes: a staleness gate that cannot run is not a green light).
STALE=0
set +e
STALE_MSG=$(python3 "${TOOLS}/level_staleness.py" "${GAME}" 2>&1)
STALE_RC=$?
set -e
case "$STALE_RC" in
    0) ;;
    2) STALE=1 ;;
    *) echo "$STALE_MSG"; echo "ERROR: tools/level_staleness.py failed (rc=${STALE_RC})."; exit 1 ;;
esac

if [[ "$STALE" == "1" ]]; then
    echo "$STALE_MSG"
    if [[ "$FAST" == "1" ]]; then
        # The loop's whole point: re-bake instead of scolding.
        #
        # ITS OUTPUT IS CAPTURED, NOT DISCARDED (2026-09-02, walkthrough finding b3).
        # This used to be `> /dev/null` with a fixed failure message that guessed at
        # the cause — "it needs the out-of-repo donors". The generators print their
        # refusals on STDOUT, so that redirect ate the ONLY actionable message in the
        # run. With one dangling `rasterRef` the author was sent hunting for donor
        # directories while the real line, which effects_gen had already written and
        # this script had already thrown away, was:
        #
        #   effects_gen: REFUSED — section_0.meta.json: rasterRef 'x' names no preset
        #   document in .../effects/presets — ... Known ids: authored_probe, ...
        #
        # A wrapper that replaces a specific diagnosis with a generic one is worse
        # than no wrapper. So: quiet on success (the loop stays quiet), and on failure
        # the re-bake's OWN OUTPUT IN FULL — not a tail, because the failing line's
        # position in the run is not knowable from here — with the donor guess demoted
        # to a footnote for the case where the output names nothing.
        # Do NOT reintroduce a redirect to /dev/null here.
        #
        # THE MARKERS BELOW ARE LOAD-BEARING. tools/test_build_fast_lanes.py lifts the
        # bytes between them and EXECUTES them against a stub re-bake that prints a
        # known refusal, which is the only way to assert "the diagnosis reaches the
        # author" rather than to assert it in prose. Keep them around the block, and
        # keep the block using only ${TOOLS} from the enclosing script.
        # >>> FAST_REBAKE_BLOCK
        echo "FAST: re-baking the level tree (tools/regenerate-level.sh)..."
        REBAKE_T0=$(date +%s)
        REBAKE_LOG=$(mktemp -t aeon-fast-rebake.XXXXXX)
        # `$?` inside `if ! cmd; then` is the INVERSION's status (always 0), so the
        # real exit code is captured here instead of reported as a confident zero.
        set +e
        "${TOOLS}/regenerate-level.sh" > "${REBAKE_LOG}" 2>&1
        REBAKE_RC=$?
        set -e
        if [[ "${REBAKE_RC}" -ne 0 ]]; then
            echo
            echo "ERROR: the FAST re-bake failed (rc=${REBAKE_RC}). ITS OWN OUTPUT FOLLOWS —"
            echo "  that is the actionable message; this wrapper knows nothing it does not."
            echo "--------------------------- tools/regenerate-level.sh ---------------------------"
            cat "${REBAKE_LOG}"
            echo "---------------------------------------------------------------------------------"
            echo "  Iterate on it directly with: tools/regenerate-level.sh"
            echo "  If nothing above names a file or an id, suspect the out-of-repo donors"
            echo "  (sonic_hack + skdisasm / AEON_SKDISASM_DIR) — but read the output first."
            rm -f "${REBAKE_LOG}"
            exit 1
        fi
        rm -f "${REBAKE_LOG}"
        REBAKE_SECS=$(( $(date +%s) - REBAKE_T0 ))
        echo "FAST: re-bake done in ${REBAKE_SECS}s."
        # <<< FAST_REBAKE_BLOCK
    else
        echo
        echo "ERROR: the committed level tree is STALE — it was not baked from the editor"
        echo "  sources that are here now. That is a SAVE, an ADD, a RENAME or a DELETE:"
        echo "  the message above names which arm fired and, for a set change, which files."
        echo "  The build consumes games/${GAME}/data/generated/ DIRECTLY (prebuild.sh is a no-op),"
        echo "  so building now would ship the PREVIOUS level data with no other warning."
        echo
        echo "  REMEDY:  tools/regenerate-level.sh     (then commit the regenerated tree,"
        echo "                                          INCLUDING the editor-source stamp)"
        echo "           FAST=1 ./build.sh ${GAME}     (dev loop: re-bakes automatically, skips gates)"
        echo
        echo "  NOT a remedy: \`touch\`. Deleting an editor document lowers no mtime, so"
        echo "  touching a file only silences the timestamp arm — the tree stays stale and"
        echo "  the same build error comes back. See tools/level_staleness.py's docstring."
        echo
        exit 1
    fi
fi

# THE FAST LOOP'S SEAM PRE-CHECK (2026-09-02, walkthrough finding b4).
#
# Binding a raster preset to a section no preset threads the chooser for is a
# canonical-build REFUSAL (7 tools/test_effects_seam_gate.py failures) that FAST used
# to be completely blind to: FAST sets NO_LINT=1, which skips the pytest lane, and the
# post-build seam gate is under `FAST == 0`. So the iteration loop went green on a tree
# the real build rejects, and the author found out at landing time, after the work.
#
# WHY A PRE-CHECK AND NOT THE WHOLE GATE. The gate's steps 1/2/2b read source only and
# cost 0.014 s (measured 2026-09-02, 5 runs including interpreter startup, against a
# 2.07 s FAST build on the same loaded box) — cheap enough to be unconditional and to run
# BEFORE the build, so the failure arrives immediately. Step 3 reads the build's listing
# and therefore cannot run before the build at all. FAST's value IS its speed; this buys
# the whole authoring-error class for under 1% of the budget.
#
# WHAT IT DOES NOT CATCH, so the green line is not over-read: reachability. It cannot
# tell whether the generated binding module reached the ROM — that is step 3, it needs
# the listing, and only the canonical `./build.sh` runs it. FAST remains not a
# merge/ship artifact, and the banner still says so.
#
# sonic4 only (demo has no act descriptor and no editor scenes), and it runs AFTER the
# re-bake above so it reads the tree the build is about to consume.
if [[ "$FAST" == "1" && "${GAME}" == "sonic4" ]]; then
    echo "FAST: checking the editor-scene binding seam (source only)..."
    if ! python3 "${TOOLS}/effects_seam_gate.py" --source-only; then
        echo
        echo "ERROR: the editor-scene binding seam is broken in the SOURCE — see above."
        echo "  The canonical ./build.sh refuses this tree too (and with more checks), so"
        echo "  fixing it now is strictly cheaper than finding it at landing time."
        exit 1
    fi
fi

# Per-game content generators (optional)
if [[ -x "games/${GAME}/prebuild.sh" ]]; then
    "games/${GAME}/prebuild.sh"
fi

echo "Generating compression self-test vectors..."
python3 "${TOOLS}/gen_compression_vectors.py"

if [[ "${NO_LINT:-0}" == "0" ]]; then
    echo "Linting..."
    if ! python3 "${TOOLS}/s4lint.py" "${MAIN_ASM}"; then
        echo "Lint errors found — fix before assembling."
        exit 1
    fi

    # Effects budget model vs the shipped code (closes EFX-9). This gate existed, was
    # CORRECT, and was invoked by NOTHING — not this script, not CI — so the only
    # references to it in the tree were its own unit test and two comments in the model
    # describing the gate as though it ran. `raster_state_bytes` drifted 10 bytes past a
    # bug-ledger entry that credited this very check with preventing drift.
    #
    # It reads .emp constants and compares them to tools/effects_budget_model.toml, so it
    # depends on source only and is cheap. It sits under the same NO_LINT guard as the
    # other source gates, so the escape hatch is `./build.sh <game> --no-lint` — note the
    # GAME IS POSITIONAL ($1), so `./build.sh --no-lint` parses --no-lint as the game name
    # and fails with `unknown --game`. That is pre-existing arg-parsing behaviour, not
    # this gate's, but it is the first thing anyone reaching for the hatch will hit.
    echo "Checking the effects budget model..."
    if ! python3 "${TOOLS}/effects_budget_check.py"; then
        echo "Budget-model drift — update tools/effects_budget_model.toml to match the code."
        exit 1
    fi

    # The tool-suite unit tests. WIRED 2026-08-16, because they were the tree's largest
    # run-by-nothing gate: 18 files, ~984 assertions, no pytest.ini, no conftest, no
    # caller. When finally run, one was red — and the red one was MASKING a real 30-byte
    # drift in RASTER_STATE_SIZE (it threw before reaching its own assertion, so the
    # stale literal underneath was never evaluated). That is the exact failure mode this
    # tree keeps rediscovering: a gate nobody runs is documentation with a shebang.
    #
    # It belongs in build.sh and not in effects_gates.py because it boots no emulator and
    # costs ~2 s; the emulator-backed gates cannot go here for precisely the opposite
    # reason. Same NO_LINT hatch as the source gates above.
    #
    # A missing pytest is a WARNING, not a failure: it is a dev-machine dependency, and
    # hard-failing here would make the build unrunnable on a box that only wants a ROM.
    #
    # BAR 25 — "does the gate's own name appear in the build's own log?" For this lane
    # the answer was NO: `-q --no-header` prints dots and "N passed", so no test FILE is
    # ever named on a green run. A file that silently stopped being collected — renamed,
    # moved, or shadowed by an import error in a sibling — is indistinguishable from one
    # that ran and passed. Collection here is a DIRECTORY SWEEP, so the cheap honest
    # check is the sweep's extent: the count below is computed by the same rule pytest
    # collects by, and a file dropping out of the lane moves it.
    if python3 -c "import pytest" 2>/dev/null; then
        echo "Running the tool-suite unit tests..."
        echo "  sweeping $(find "${TOOLS}" -maxdepth 1 -name 'test_*.py' | wc -l) test file(s) under ${TOOLS}"
        if ! python3 -m pytest "${TOOLS}" -q --no-header -p no:cacheprovider; then
            echo "Tool-suite tests failed — the build tooling is broken, not just the ROM."
            exit 1
        fi
    else
        echo "  (pytest not installed — skipping tool-suite tests)"
    fi

    # The expect-fail lane (Parcel R1 Task 7): poison .emp modules under
    # games/sonic4/test/poison/ that MUST fail to build, asserted by
    # tools/emp_expect_fail.py. It gates the poisons listed there plus the permanent sentinel
    # case, each with its own expected diagnostic-message fragment AND expected
    # [Error] count. Each case is one real build invocation with the poison named
    # as `sigil build --extra-entry <module>`, so the poison elaborates inside
    # the real profile (same manifest rewrites, same -D values) without any
    # file's body being rewritten — see tools/emp_expect_fail.py's docstring and
    # games/sonic4/test/poison/README.md. Same NO_LINT hatch as the other source
    # gates.
    echo "Running the expect-fail lane..."
    if ! python3 "${TOOLS}/emp_expect_fail.py"; then
        echo "expect-fail lane failed — a poison module built clean or a guard's message drifted."
        exit 1
    fi
fi

# STRESS_ART throwaway re-bake: regenerate the uniquified act pool IN PLACE under an
# EXIT trap that restores the committed tree from git (covers success AND set -e
# failures). Requires donors (like regenerate-level.sh). verify_level_bin below then
# runs against the stress tree (it stays internally consistent), and the sigil build
# links the uniquified pool into s4.stressart.bin.
if [[ "${STRESS_ART:-0}" == "1" ]]; then
    STRESS_GEN_TREE="games/sonic4/data/generated/ojz/act1"
    STRESS_COLL_TREE="games/sonic4/data/collision"
    if [[ -n "$(git status --porcelain -- "$STRESS_GEN_TREE" "$STRESS_COLL_TREE")" ]]; then
        echo "ERROR: STRESS_ART needs a clean generated tree, but git status shows changes"
        echo "  under $STRESS_GEN_TREE or $STRESS_COLL_TREE. Commit or stash them first —"
        echo "  the stress re-bake restores from git and would discard uncommitted changes."
        exit 1
    fi
    _restore_stress_tree() {
        echo "STRESS_ART: restoring the committed level tree from git..."
        git checkout -q -- "$STRESS_GEN_TREE" "$STRESS_COLL_TREE" 2>/dev/null || true
        git clean -fdq -- "$STRESS_GEN_TREE" 2>/dev/null || true
    }
    trap _restore_stress_tree EXIT
    echo "STRESS_ART: throwaway re-bake with uniquified act pool (N=${STRESS_ART_N:-2600})..."
    STRESS_UNIQUIFY="${STRESS_ART_N:-2600}" "${TOOLS}/regenerate-level.sh"
fi

# The committed OJZ level tree is consumed directly (its generators need
# out-of-repo donors — tools/regenerate-level.sh). Fail LOUDLY on internal
# drift (hand-edited head, missing blob, stale .zx0) the whole-ROM gate would
# only catch after the ROM already moved.
if [[ "$FAST" == "0" ]]; then
echo "Verifying committed OJZ level tree..."
if ! python3 "${TOOLS}/verify_level_bin.py"; then
    echo "Level-tree drift — re-bake with tools/regenerate-level.sh, then rebuild."
    exit 1
fi

# The editor-effects drift gate (scanline P5 slice 5). The generated binding
# module is a COMMITTED artifact act_descriptor.emp imports, so both failures
# are real: a hand edit inside it, and an editor scene / `sceneRef` changed
# without a re-bake. Unlike the level tree this reads only in-repo inputs (no
# donor, no compressor), so regenerating in memory and comparing costs
# milliseconds and can run on every build rather than only at re-bake time.
if ! python3 "${TOOLS}/effects_gen.py" check; then
    echo "Editor-effects drift — re-bake with tools/regenerate-level.sh, then rebuild."
    exit 1
fi

# Collision height/angle consistency (2026-08-28). Two shipped defects were
# invisible to every other check here: a flat floor slab whose angle byte claimed
# 45 degrees (the glide momentum trap), and floor cells with a 1 px hole in their
# height profile (the false-ledge teeter). Both are contradictions between a
# cell's GEOMETRY and its METADATA, derived from what player_sensors.emp's
# probe_core actually does with the pair — not a list of known-bad values.
#
# Reads only committed artifacts (the baked sec*_strips_a.bin plus the interned
# collision tables), so it runs on every canonical build rather than only at
# re-bake time, and it REFUSES to pass on an empty population.
#
# --baseline exempts the violations already in the tree, whose repaint is HELD
# (it lands in the owner's live editor tree — tools/repaint_ojz_collision.py).
# NEW violations still fail. Delete entries from that file as they are cleared;
# when it reaches an empty list, drop the file and this flag.
# sonic4 only: games/demo has no collision data, and running it there would be a
# vacuous pass on another game's tree.
if [[ "${GAME}" == "sonic4" ]]; then
    if ! python3 "${TOOLS}/collision_consistency.py" \
             --baseline "${TOOLS}/collision_baseline.json"; then
        echo "Collision data is inconsistent — see above."
        echo "  Held repaint:  python3 tools/repaint_ojz_collision.py   (check mode)"
        exit 1
    fi
fi
fi

# Art-pool ROM budget report + gate (art-streaming Phase 2). Level art is now
# capped by ROM, not VRAM — a non-resident page streams in on demand — so the
# pool's ROM footprint is the budget that matters. Report per act (raw bytes,
# stored bytes per form, page count, ratio); warn above ART_ROM_SOFT_KB, fail
# above ART_ROM_HARD_KB (per-act overridable: ART_ROM_{SOFT,HARD}_KB_<ACT>;
# OJZ defaults 24/64 KB). Under STRESS_ART the pool is a throwaway uniquified
# fixture that deliberately overwhelms the cache, so report-only (no gate).
ART_ROM_REPORT_FLAGS=""
if [[ "${STRESS_ART:-0}" == "1" ]]; then ART_ROM_REPORT_FLAGS="--no-fail"; fi
if [[ "$FAST" == "0" ]]; then
if ! python3 "${TOOLS}/art_rom_report.py" . ${ART_ROM_REPORT_FLAGS}; then
    echo "Art-pool ROM budget exceeded — see the per-act report above."
    exit 1
fi
fi

# THE BUILD: one sigil invocation — assemble -> declared-order link -> emit_rom
# (checksum folded) -> sigil-canonical .lst -> ROM.
#
# ⚠ CORRECTED 2026-09-04, MEASURED. This comment used to end "DEBUG additionally gets
# the convsym deb2 appendix; release ships the assembled image alone (item 29)". The
# release ROM carries the appendix too: `s4.bin` holds 41761 bytes past `EndOfRom`
# ($0A5C82) beginning with the ASCII magic `deb2`. CLAUDE.md's own crash-report ruling
# (2026-08-04) says so — "both carry the MD Debugger island + deb2 symbols" — and this
# line had outlived it. Found while root-causing a release CRC that moved: adding
# symbols to a DEBUG-gated block changes the RELEASE ROM's bytes, because the symbol
# NAMES land in that appendix. The assembled image [0, EndOfRom) was byte-identical
# apart from the header checksum word at $18E, which follows any content change.
# Whoever next reads a moved release CRC should split it at EndOfRom before calling it
# a regression.
if [[ "${STRESS_EVICT:-0}" == "1" ]]; then
    # The stress fixture fixes the shape (sonic4 debug + STRESS_EVICT define); it does
    # NOT combine with --game/--debug (the CLI rejects that).
    NATIVE_FLAGS="--stress-evict"
elif [[ "${STRESS_ART:-0}" == "1" ]]; then
    # The stress-art fixture fixes the shape (sonic4 debug + fixture placement) against
    # the uniquified pool re-baked above; --stress-art selects the fixture-scoped derived
    # placement (greedy pack from measured sizes, org anchors held). It does NOT combine
    # with --game/--debug (the CLI rejects that).
    NATIVE_FLAGS="--stress-art"
else
    NATIVE_FLAGS="--game ${GAME}"
    if [[ "${DEBUG:-0}" == "1" ]]; then NATIVE_FLAGS="${NATIVE_FLAGS} --debug"; fi
fi
# CONTRACT CLOSURE GATE — default ON.
#
# `sigil build` runs the whole-corpus contract closure before it links. The
# closure needs the whole call graph, so it cannot be a per-file check; this is
# where it gates. A firing outside the frozen baseline fails the build with the
# list, and so does a baseline row that STOPS firing — a silently narrowing
# analysis is the destructive direction, not a free pass.
#
# CONTRACTS=0 is the EMERGENCY OPT-OUT, not a normal knob. It exists so a
# contract-checker defect cannot block shipping a ROM; using it means the build
# is not contract-checked, and the skip says so on stderr. Reach for it only when
# the gate itself is wrong, and open a ledger row when you do.
if [[ "${CONTRACTS:-1}" == "0" ]]; then
    export SIGIL_CONTRACTS=0
fi

echo "Building ${MAIN_ASM} (sigil)..."
# The instant the subject is born: the post-sigil listing gates below assert that
# the listing AND the ROM post-date this (bganim_room --built-after). Whole seconds
# from `date +%s` truncate DOWN, so a file written in the same second still passes.
SIGIL_T0=$(date +%s)
"${SIGIL_BUILD}" build --aeon . --native ${NATIVE_FLAGS} \
    -o "${ROM_NAME}.bin" --emit-lst "${ROM_NAME}.lst"

ROM_SIZE=$(stat -c%s "${ROM_NAME}.bin")
ROM_KB=$(awk "BEGIN {printf \"%.1f\", ${ROM_SIZE}/1024}")
ROM_PCT=$(awk "BEGIN {printf \"%.1f\", ${ROM_SIZE}/4194304*100}")
echo "Build complete: ${ROM_NAME}.bin — ${ROM_SIZE} bytes (${ROM_KB} KB, ${ROM_PCT}% of 4MB)"

# The listing-reading gates. The `-f` guard that used to wrap this block made a
# MISSING listing a silent skip of s4budget, the seam gate and the BG-anim ceiling
# together; sigil was asked for `--emit-lst` two screens up, so its absence here is
# a build bug and is named as one (2026-08-26, listing-provenance fix).
if [[ "$FAST" == "0" && ! -f "${ROM_NAME}.lst" ]]; then
    echo "ERROR: ${ROM_NAME}.lst is missing after the sigil build — nothing produced the"
    echo "  listing this invocation's gates read (s4budget, effects_seam_gate, bganim_room)."
    echo "  sigil was invoked with --emit-lst ${ROM_NAME}.lst; a missing listing is a build"
    echo "  bug, not a bootstrap condition. Do not convert this to a skip."
    exit 1
fi
if [[ "$FAST" == "0" ]]; then
    # NOT `|| true`. It was, and that mattered: s4budget returned 0 on every path
    # anyway (tools lens sweep D7), so the budgets were gated by nothing twice over
    # — no threshold in the tool, and its exit code discarded here. The tool now
    # returns 1 on a real ROM / object-bank / RAM-into-stack breach, so let that
    # fail the build.
    #
    # --map is REQUIRED for the budget axis: the [[budget]] ceilings and their
    # cursor symbols are declared in the game's placement contract, which is what
    # replaced the retired `__BUDGET_*` sentinels the AS-era parser looked for. A
    # path given here that does not exist is a hard error inside the tool rather
    # than a silent downgrade to "UNMEASURED".
    if ! python3 "${TOOLS}/s4budget.py" "${ROM_NAME}.lst" "${ROM_NAME}.bin" \
            --map "games/${GAME}/map.toml" --summary; then
        echo "Budget exceeded — see the s4budget output above."
        exit 1
    fi

    # THE ROW REMAP LADDER'S INVARIANTS, on the emitted bytes (EFFECTS-W1 item 9).
    # Post-sigil, with the same --built-after provenance rule as the goldens below, for the
    # same reason: the pytest lane runs BEFORE the build, so a unit test opening s4.bin would
    # check a previous invocation's ladder.
    #
    # WHAT ONLY THE ROM CAN ANSWER. The three invariants (entry[i] >= i, non-decreasing,
    # entry[i] <= 2i) hold BY CONSTRUCTION in row_remap_ladder64() — and "the generator is
    # right" is a different claim from "those bytes reached the image at the address the band
    # record points at", which is what the 68000 indexes through. It also refuses an
    # ALL-IDENTITY ladder, which the three invariants cannot see (entry[i] = i satisfies every
    # one of them) and which would spend the pass's cycles writing the buffer back unchanged.
    #
    # RUN FOR BOTH GAMES, DELIBERATELY OUTSIDE THE sonic4 ARM BELOW. demo declares no
    # CAP_ROW_REMAP, and the gate's undeclared path is not a skip — it asserts that demo's
    # image carries NEITHER a ladder symbol NOR a non-NULL remap tail, in both directions.
    # That is the shape this capability actually threatens demo in: BAND_REMAP_N is
    # ENGINE-WIDE, so demo's band record widened for it, and a gate that only looked at
    # sonic4 would be blind to a pointer leaking into the game that can never use one.
    if ! python3 "${TOOLS}/row_remap_gate.py" --lst "${ROM_NAME}.lst" \
            --rom "${ROM_NAME}.bin" --built-after "${SIGIL_T0}" --game "${GAME}"; then
        echo "Row remap ladder — see above (tools/row_remap_gate.py, the post-sigil gate)."
        exit 1
    fi

    # The row remap's ART half (EFFECTS-W1 item 9d): the ROM source image, the gather's own
    # geometry immediates, and the publication that wires the two halves together.
    #
    # WHY IT IS A SECOND GATE AND NOT AN ARM OF THE ONE ABOVE. That one asks whether the
    # LADDER is safe and is the model's; this asks whether the IMAGE and the LOOP THAT
    # INDEXES IT agree with each other and with the declared VRAM map. Its decisive arm
    # decodes five immediates out of Waterline_Art_Update's own instruction bytes, which is
    # the only place the "image and gather changed apart" failure is visible: a stale stride
    # reads plausible pixels from the wrong rows and every byte-level check stays green.
    #
    # RUN FOR BOTH GAMES, for the reason above: the gather is ENGINE code and ships in every
    # game, so the undeclared path is not a skip — it asserts demo's image carries NO source
    # art AND a Waterline_Art_Update that is exactly `rts`.
    if ! python3 "${TOOLS}/waterline_art_gate.py" --lst "${ROM_NAME}.lst" \
            --rom "${ROM_NAME}.bin" --game "${GAME}"; then
        echo "Waterline art half — see above (tools/waterline_art_gate.py, the post-sigil gate)."
        exit 1
    fi

    # The editor-scene binding seam's REACHABILITY gate (scanline P5 slice 5).
    # Reads the listing because that is the only place the answer exists: an
    # unreached `.emp` module still parses, still scans, and still builds green
    # with `ensure(1 == 0)` inside it, so no source-level check can tell whether
    # act_descriptor.emp's import edge is live. The generated module's `pub equ`
    # witnesses are defined only when it is lowered, so their presence here is the
    # evidence. sonic4-only: `demo` has no act descriptor and no editor scenes.
    if [[ "${GAME}" == "sonic4" ]]; then
        if ! python3 "${TOOLS}/effects_seam_gate.py" --lst "${ROM_NAME}.lst"; then
            echo "Editor-scene binding seam is not reached — see above."
            exit 1
        fi

        # THE PALETTE BYTE GOLDEN (EFFECTS-W1 item 5). An Aurora-authored `cycles` /
        # `variants` key lowers through the engine's own constructors into a `pub data`;
        # this gate reads that record back OUT OF THIS ROM, at this listing's addresses,
        # and decodes it against the JSON the author wrote — including the one place the
        # generator does NOT forward verbatim, the `period - 1` the document's FRAMES unit
        # costs (ruling Q7). It also holds the worked document byte-for-byte against the
        # hand `pub data` twin it re-expresses.
        #
        # It runs HERE, below sigil, for bganim_room's reason: the pytest lane runs BEFORE
        # the build, so a unit test opening s4.debug.bin would measure a previous build.
        # --built-after makes a stale artifact a named UNMEASURABLE (exit 2) instead.
        #
        # It is PYTHON and not a comptime `ensure` deliberately: the hand twin resolves as
        # a LABEL inside an `.emp` array literal, so the natural
        # `first_mismatch([<hand>], [<generated>]) == -1` guard is ALWAYS RED on correct
        # code — and flipping it to `== 0` to "fix" that makes it permanently vacuous in
        # one keystroke. Measured, docs/superpowers/probes/2026-09-02-item5-comptime-probe.md.
        if ! python3 "${TOOLS}/editor_palette_golden.py" --lst "${ROM_NAME}.lst" \
                --rom "${ROM_NAME}.bin" --built-after "${SIGIL_T0}"; then
            echo "Editor palette golden failed — see above (tools/editor_palette_golden.py)."
            exit 1
        fi

        # THE BAND-DRIFT BYTE GOLDEN (EFFECTS-W1 item 3). The scanline_spans differential
        # in tools/effects_gates.py proves the three `cap_band_drift_*` instruction spans
        # are emitted for sonic4 and elided for demo; this proves the DATA those spans
        # read — the 16.16 rate in each band record's drift tail — is the rate
        # games/sonic4/data/effects/ojz_scenes.emp authors. Neither implies the other: a
        # walker that faithfully accumulates a rate of ZERO emits the same spans, costs
        # the same cycles, and moves no pixel.
        #
        # It runs HERE for editor_palette_golden's reason (the pytest lane runs BEFORE the
        # build, so a unit test opening s4.bin would grade a previous one), and it reads
        # the ROM rather than asserting in `.emp` for a structural reason: the equivalence
        # witness's `band_eq()` runs through `.br_base` and is blind to every capability
        # tail by construction.
        if ! python3 "${TOOLS}/band_drift_golden.py" --lst "${ROM_NAME}.lst" \
                --rom "${ROM_NAME}.bin" --built-after "${SIGIL_T0}"; then
            echo "Band-drift golden failed — see above (tools/band_drift_golden.py)."
            exit 1
        fi

        # THE MID-FRAME NAMETABLE-BASE BYTE GOLDEN (EFFECTS-W1 item 11a). `OJZ_BaseSwap`
        # is one OP_SET_REG that re-points Plane A's base at Plane B's nametable partway
        # down the frame; this reads its 11 words back OUT OF THIS ROM at this listing's
        # address and holds the register word against a byte re-derived from
        # engine/system/constants.emp's VRAM_PLANE_B and engine/vdp.emp's own
        # `vdp_base_shift` arm — the same fold boot_data.emp derives reg $02 from.
        #
        # The `.emp` fixture's `first_mismatch` pin cannot answer this: it compares the
        # encoder against a hand twin, both comptime, and would stay green with the
        # `pub data` emitting nothing at all. Same post-sigil placement and same
        # --built-after provenance rule as the two goldens above.
        #
        # --shape IS PASSED, NOT SNIFFED, and the two shapes assert OPPOSITE things: the
        # words present in DEBUG, and the symbol emitting ZERO bytes in release, because
        # its only installer (Debug_BandDemoHotkey) emits zero release bytes and an
        # unconditional program would be a dormant scaffold in the shipped ROM.
        BASE_SWAP_SHAPE="release"
        if [[ "${DEBUG:-0}" == "1" ]]; then BASE_SWAP_SHAPE="debug"; fi
        if ! python3 "${TOOLS}/plane_base_swap_gate.py" --lst "${ROM_NAME}.lst" \
                --rom "${ROM_NAME}.bin" --built-after "${SIGIL_T0}" \
                --shape "${BASE_SWAP_SHAPE}"; then
            echo "Mid-frame plane-base gate failed — see above (tools/plane_base_swap_gate.py)."
            exit 1
        fi

        # THE REELS BYTE GOLDEN (EFFECTS-W1 item 10a). `OJZ_Reel_Speed` is
        # REEL_BAND_COUNT independently-authored, pairwise-distinct per-frame phase
        # increments — the "reel source" `OJZ_Reels_Fill` advances every frame and
        # composes onto the per-column VSRAM buffer's BG words, so adjacent 16-px strips
        # scroll at genuinely different rates instead of the shared-phase deform table's
        # lag. This reads the table's bytes back OUT OF THIS ROM and holds them against
        # values re-parsed from games/sonic4/data/effects/ojz_effects.emp's own
        # OJZ_REEL_SPEEDS array and games/sonic4/config/constants.emp's REEL_BAND_COUNT —
        # and proves OJZ_Reels_Fill itself (the code, not just its data) reaches the ROM.
        #
        # The `.emp` `ensure`s (distinctness, the length identity) are comptime-vs-
        # comptime and would stay green with the `pub data`/`pub proc` emitting nothing
        # at all — the same gap plane_base_swap_gate.py's header names for OJZ_BaseSwap.
        # Same post-sigil placement and same --built-after provenance rule as the goldens
        # above.
        #
        # --shape IS PASSED, NOT SNIFFED, same reason as the base-swap gate: nothing in
        # the release shape can ever set OJZ_Reel_Active (its only writer is
        # tools/reels_witness.py poking a DEBUG-only RAM cell directly — there is no
        # hotkey, Debug_BandDemoHotkey's own header enumerates the exhausted pad chords),
        # so an unconditional emission would be a dormant scaffold in the shipped ROM.
        REELS_SHAPE="release"
        if [[ "${DEBUG:-0}" == "1" ]]; then REELS_SHAPE="debug"; fi
        if ! python3 "${TOOLS}/reels_gate.py" --lst "${ROM_NAME}.lst" \
                --rom "${ROM_NAME}.bin" --built-after "${SIGIL_T0}" \
                --shape "${REELS_SHAPE}"; then
            echo "Reels gate failed — see above (tools/reels_gate.py)."
            exit 1
        fi

        # THE PLANE-ROLE-SWAP BYTE GOLDEN (EFFECTS-W1 item 10b). Disassembles
        # Parallax_Set_Roles_Swapped and asserts its four (register, value) writes
        # match engine/system/constants.emp (VRAM_PLANE_A/VRAM_PLANE_B) and
        # engine/vdp.emp's vdp_base_shift (PlaneA AND PlaneB arms) — the fold item
        # 11a's OJZ_BaseSwap also derives its word through. UNLIKE the two golden
        # gates above, this one asserts the SAME thing in both shapes (present and
        # correct): the mechanism is unconditional real engine capability, not a
        # DEBUG-only effects-lab demonstration, so there is no release-shape
        # zero-byte arm to check. --shape is still passed, for messaging only.
        ROLE_SWAP_SHAPE="release"
        if [[ "${DEBUG:-0}" == "1" ]]; then ROLE_SWAP_SHAPE="debug"; fi
        if ! python3 "${TOOLS}/plane_role_swap_gate.py" --lst "${ROM_NAME}.lst" \
                --rom "${ROM_NAME}.bin" --built-after "${SIGIL_T0}" \
                --shape "${ROLE_SWAP_SHAPE}"; then
            echo "Plane-role-swap gate failed — see above (tools/plane_role_swap_gate.py)."
            exit 1
        fi

        # The BG-animation section's ROOM, re-derived from THIS build's listing
        # (decision d-9). `ojz_bg_anim` grows into the hole that ends
        # at the `dac_banks` map anchor — DERIVED by the bank placement rule since the
        # 2026-08-26 re-layout, not the hard `$48000` this comment used to name — which
        # is also the only room
        # `Art_Sonic` has to grow into — so the ceiling authors are held to has to be
        # re-checked against the layout, not pinned once and trusted.
        #
        # It runs HERE, after the build, because the answer only exists in the
        # listing: the frozen boundary table lists a SUBSET of labels, so a gap in it
        # is an allotment and never proven free space (docs/OVERSEER.md — the bar
        # three parties broke in one afternoon). sonic4-only: `demo` places no
        # `ojz_bg_anim` section at all. The ROM room is the ONLY placement limit
        # since sigil b0363140 (derived layout): the former "placer room" arm is
        # retired (docs/DEFERRED_WORK.md, "DEFECT 2 (BGANIM-PLACE)" closure note).
        #
        # THIS IS THE ONLY ENFORCEMENT of BGANIM_SECTION_CEILINGS against a real
        # listing (2026-08-26). --rom/--built-after: the listing and the ROM must both
        # post-date SIGIL_T0, the instant this invocation started sigil — the sigil
        # listing carries no ROM identity of its own, so temporal provenance is the
        # check it supports, and it excludes a prior build's or another profile's
        # listing by construction. --fixture: the unit tests run over a committed cut
        # of a real listing, which nothing re-derives; every row of that cut must be
        # re-found here with the same lexical shape, so an emitter format change is a
        # named "fixture is stale" failure and not a unit test green against the past.
        if ! python3 "${TOOLS}/bganim_room.py" --lst "${ROM_NAME}.lst" \
                --rom "${ROM_NAME}.bin" --built-after "${SIGIL_T0}" \
                --fixture "${TOOLS}/fixtures/bganim_room_excerpt.lst" --gate; then
            echo "BG-animation section room — see above (tools/bganim_room.py, the post-sigil gate)."
            exit 1
        fi

        # The DPLC Important-queue SLOT cost, which is NOT the entry count the
        # `dplc_peak_entries` ensures bound. A transfer whose ROM source crosses a
        # $20000 boundary is SPLIT into two queue entries by QueueDMA
        # (engine/system/dma_queue.emp `.split`), so a frame costs
        # entries + straddles slots, and whether an entry straddles depends on
        # where the art LANDED — a link-time fact no comptime `ensure` can see,
        # because `dplc_peak_entries` parses the blob and never learns the base.
        #
        # It runs HERE, after sigil, for exactly that reason: the base addresses
        # only exist in the listing. The gate holds the measured peak slot cost at
        # or under the committed `dplc_peak_entries(_dplc_sonic) <= N` ratchet in
        # collision_data.emp, so a placement change that pushes a peak frame onto a
        # boundary is a named build failure instead of a silent extra slot charged
        # against DPLC_ENTRY_RESERVE. The ratchet is READ from that ensure, not
        # copied here. --selftest (not run in the build) proves the gate red by
        # searching for a shift that trips it. sonic4-only: `demo` has no player.
        #
        # It takes the ROM as well as the listing because it now splits each
        # character's straddling frames into REACHABLE and unreachable, and the
        # reachable set is walked out of the BUILT animation tables (plus the
        # tilt/bank expansions and every other mapping_frame writer, found by
        # scanning the tree). A straddle on a frame the game can display is a
        # second, named failure; a writer it cannot classify WIDENS the set and
        # says so, never narrows it.
        # Measured and reasoned in docs/2026-08-30-dplc-append-disturbance.md.
        if ! python3 "${TOOLS}/dplc_straddle.py" --lst "${ROM_NAME}.lst" \
                     --rom "${ROM_NAME}.bin" --gate; then
            echo "DPLC straddle gate failed — see above (tools/dplc_straddle.py)."
            exit 1
        fi

        # The ground-angle sprite tilt, checked by EXECUTING the routine this build
        # just emitted. The claim the tilt parcel makes is not "it assembles" but
        # "the selected mapping frame is a function of the terrain angle, at the S3K
        # octant boundaries, with facing folded in the direction that does not mirror
        # one side" — and no source-level check and no gate over shipped level content
        # can answer that (nothing authored in OJZ reaches most of the octants; see
        # docs/research/loops-and-sprite-rotation.md). So the gate takes
        # Player_ApplyTilt's extent from THIS listing, its bytes from THIS ROM,
        # decodes them with capstone (an independent decoder, not our own assembler's
        # opinion of what it emitted), executes them over a sweep of angles, facings,
        # animation cursors and all three characters' shipped scripts, and compares
        # against the S3K model re-derived from sonic3k.asm:24808-24862.
        #
        # It runs HERE, below sigil, for the same reason bganim_room does: build.sh's
        # pytest lane runs BEFORE the build, so a unit test opening s4.debug.bin would
        # measure a previous build (build.sh:61-72 — that happened twice). The unit
        # tests run over a COMMITTED cut instead, and --fixture makes a stale cut a
        # named failure here rather than a green against the past.
        #
        # The executor models one instruction form per line the routine contains and
        # RAISES on anything else, so a future edit reaching for a new addressing mode
        # stops the build instead of being silently skipped. That refusal is the only
        # reason its green is worth anything.
        if ! python3 "${TOOLS}/sprite_tilt_gate.py" --lst "${ROM_NAME}.lst" \
                --rom "${ROM_NAME}.bin" --built-after "${SIGIL_T0}" \
                --fixture "${TOOLS}/fixtures/sprite_tilt_cut.json" --gate; then
            echo "Sprite-tilt gate failed — see above (tools/sprite_tilt_gate.py)."
            exit 1
        fi

        # The two ABILITY-HOOK preconditions, checked the same way and for a sharper
        # reason: the claim is a REFUSAL — "a jump press made after walking off a ledge
        # must NOT fire the ability" — and the recorded replay net demonstrably cannot
        # see it. For Sonic's insta-shield that net is byte-identical across the parcel
        # that added the gate (measured, both fixtures), because every airborne press it
        # holds was already made out of a real jump; for Tails' flight the net cannot
        # reach the routine AT ALL (Character_ID is boot-zero = CHAR_SONIC and its only
        # writer, Debug_CharacterHotkey, stands down for INPUT_PLAYBACK and INPUT_RECORD
        # alike). So the subject is the ROUTINE: extent from THIS listing, bytes from
        # THIS ROM, capstone as an independent decoder, and a sweep over all 256
        # player_state values —
        #   Ability_InstaShield  x the three one-shot values x the suppression bits,
        #     vs S3K's Sonic_JumpHeight -> Sonic_ShieldMoves (sonic3k.asm:23368-23486)
        #   Ability_TailsFlight  x the release-cap probes x the y_vel probes derived
        #     from each, vs Tails_JumpHeight -> Tails_Test_For_Flight (:28596-28693)
        # The allowed set each must produce is exactly {PSTATE_JUMP, PSTATE_ROLLJUMP}.
        # Ability_KnuxGlide is deliberately NOT a subject — the ruling left the glide on
        # the broad "any air state" rule (coyote time), so asserting the gate for it
        # would assert a rule the engine does not have. Same post-sigil placement and
        # same --fixture discipline as the two gates above (one fixture FILE per
        # subject, so re-stamping one cannot quietly re-stamp the other). sonic4-only:
        # `demo` has no player.
        if ! python3 "${TOOLS}/instashield_gate.py" --lst "${ROM_NAME}.lst" \
                --rom "${ROM_NAME}.bin" --built-after "${SIGIL_T0}" \
                --fixture "${TOOLS}/fixtures/instashield_cut.json" \
                --tails-fixture "${TOOLS}/fixtures/tailsflight_cut.json" --gate; then
            echo "Ability jump-gate check failed — see above (tools/instashield_gate.py)."
            exit 1
        fi

        # The loop crossover's READ side, checked the same way and for the reason that
        # forced the shape: the claim is that a byte of CrossoverTable DECIDES a
        # player's collision plane, and every cell of every shipped act holds
        # XOVER_NONE (docs/LOOP_CROSSOVER_ENCODING.md §2.1 — all 18 plane files). So a
        # correct read site and a DELETED one emit the identical ROM, the identical
        # CRC and the identical recorded play: no gate over content can tell them
        # apart, which is the subject of that document's §8.1. This gate therefore
        # takes Player_LoopCrossover AND Collision_GetType from THIS listing, their
        # bytes and the shipped table from THIS ROM, decodes with capstone, executes
        # both (the lookup is NOT stubbed — stubbing it would assume the half worth
        # showing), and varies exactly ONE byte of the ROM's CrossoverTable to separate
        # "the value is readable" from "the value is consumed". It refuses a run in
        # which no execution was moved by that byte.
        #
        # The edge trigger gets its own family because it has a wrong version that
        # passes a naive test: the §3.3 two-way pair (plane A says TO_B where plane B
        # says TO_A at one cell) is what a layer-re-armed trigger ping-pongs on, and
        # standing still does not discriminate. Same post-sigil placement and same
        # --fixture discipline as the two gates above. sonic4-only: `demo` has no player.
        if ! python3 "${TOOLS}/loop_crossover_gate.py" --lst "${ROM_NAME}.lst" \
                --rom "${ROM_NAME}.bin" --built-after "${SIGIL_T0}" \
                --fixture "${TOOLS}/fixtures/loop_crossover_cut.json" --gate; then
            echo "Loop-crossover gate failed — see above (tools/loop_crossover_gate.py)."
            exit 1
        fi
    fi
fi

# Update ctags symbol index
if command -v ctags &>/dev/null && [[ "$FAST" == "0" ]]; then
    ctags -R .
fi

if [[ "$FAST" == "1" ]]; then
    echo "================================================================================"
    echo " FAST BUILD COMPLETE — ${ROM_NAME}.bin"
    if [[ -n "${REBAKE_SECS:-}" ]]; then
        echo "   level tree was STALE -> re-baked in ${REBAKE_SECS}s"
    else
        echo "   level tree was fresh -> no re-bake"
    fi
    echo "   VERIFICATION LANES WERE SKIPPED: s4lint · effects_budget_check · pytest tools"
    echo "   · emp_expect_fail · verify_level_bin · art_rom_report · s4budget"
    echo "   · bganim_room (BG-anim ceiling NOT checked)"
    echo "   · sprite_tilt_gate (the tilt routine is NOT executed)"
    echo "   · instashield_gate (neither ability jump-gate is executed) · ctags."
    if [[ "${GAME}" == "sonic4" ]]; then
    echo "   effects_seam_gate ran its --source-only half (seam spelling + raster binding);"
    echo "   its REACHABILITY witnesses were NOT checked — they read this build's listing."
    else
    echo "   · effects_seam_gate (sonic4 only — ${GAME} has no act descriptor)."
    fi
    echo "   · loop_crossover_gate (the crossover read site is NOT executed)."
    echo "   This is a DEV artifact. It is byte-identical to the canonical ROM on this"
    echo "   tree, but NOTHING here checked that — run ./build.sh before you land it."
    echo "================================================================================"
fi
