#!/usr/bin/env python3
"""Inject an editor-authored background over the generated zone BG.

Reads data/editor_bg_override.json ({"layout": [2048 words, blob-local
tile indices], "tiles": [[64 px]...]}) and rewrites
data/generated/ojz/act1/zone_bg.bin + bg_tiles.bin in the engine's
conventions (VRAM-absolute indices at BG_TILE_BASE_SLOT, 2-byte BE
byte-length tile blob header).

Run by build.sh after ojz_strip_gen.py when the override file exists.
"""
import json, struct, os, sys

# LOCKSTEP: the per-band record layout this tool emits (6 dc.w fields + 8
# bank pointers = 44 bytes) is mirrored by the `bganim_band` struct in
# engine/level/bg_anim.emp (`struct bganim_band`, read field-by-field by
# BgAnim_Update). A record-format change edits BOTH together.
# BG_TILE_BASE_SLOT / BG_TILE_CAPACITY are imported from the generated registry
# mirror — ONE authority (tools/vram_map.py <- games/sonic4/vram.toml), not
# restated literals (the four-copies-of-448 incident). The capacity is 448, not
# constants.asm's old 512 nominal: the sprite table ($B800) and HScroll table
# ($BC00) live in the top of the $8000-$BFFF region.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vram_map import GAME as _VRAM_MAP_GAME, BG_TILE_BASE_SLOT, BG_TILE_CAPACITY
assert _VRAM_MAP_GAME == 'sonic4', (
    f"tools/vram_map.py was generated for {_VRAM_MAP_GAME!r}, not sonic4 — "
    "regenerate: python3 tools/gen_vram_map.py --game sonic4 "
    "--toml games/sonic4/vram.toml --py tools/vram_map.py")
# BGANIM_MAX_BANDS — the band ceiling this emitter enforces, and the RELEASE defense
# for BgAnim_Update's walk over BgAnim_LastStep (bg_anim.emp's `assert.w d7, ls,
# #BGANIM_MAX_BANDS` is a DEBUG-only backstop; asserts are zero bytes in the plain
# shape). It was a bare `4` inside the assert message until 2026-08-18.
#
# THREE INDEPENDENT AUTHORITIES HOLD THIS NUMBER, and they must agree:
#   engine/system/constants.emp   pub const BGANIM_MAX_BANDS — sizes engine/ram.emp's
#                                 BgAnim_LastStep array (ram.emp names it, so the array
#                                 cannot drift from THIS one on its own)
#   engine/level/bg_anim.emp      a DELIBERATE module-local mirror — that file is lowered
#                                 STANDALONE by `bg_anim_port` against an empty symbol
#                                 table, so it may not import engine.constants (see the
#                                 note at its own const); it bounds the runtime assert
#   this file                     the emitter's cap, which is what actually keeps a
#                                 too-wide table out of the ROM
#
# They are NOT collapsible: the standalone-port constraint is real and the ram-harvest
# pass cannot reach a CODE module's consts. So this follows RASTER_MAX_PATCH's ruling
# instead — KEEP THE MIRRORS, GATE THE DRIFT. The gate is
# tools/test_bg_emit.py::TestBgAnimBandCeiling, which reads all three and fails on any
# disagreement; before it existed, raising the ceiling HERE alone would have let
# BgAnim_Update walk off the end of BgAnim_LastStep in the release shape with nothing
# to catch it. Named rather than left inline so the gate can import it instead of
# regex-scraping an assert message.
BGANIM_MAX_BANDS = 4

OUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'games', 'sonic4', 'data', 'generated', 'ojz', 'act1')
OVERRIDE = os.path.join(os.path.dirname(__file__), '..', 'games', 'sonic4', 'data', 'editor_bg_override.json')

def validate_band_coherence(anims, tiles):
    """Assert each band's slots really are the front of the static tile blob.

    Bands pack contiguously from slot 0 and DMA over the FRONT of `tiles`, so a
    band's phase-0 art IS those slots' rest state:

        phases[0] == tiles[slot_base : slot_base + cols*rows]

    Verified exactly on the two real bands the file carried at b0e5a661. This
    is the invariant that makes `anims`/`tiles`/`layout` inseparable, and it is
    asserted here because a violation bakes CLEANLY and ships silently corrupt
    art: retained bands would DMA stale phase art over whatever a newer dedup
    put in those slots. Every other assert in this file would still pass.

    Booked as docs/BUGS.md TOOL-01.
    """
    cursor = 0
    for i, a in enumerate(anims):
        n = a['cols'] * a['rows']
        base = a.get('slot_base', cursor)
        assert base == cursor, (
            f'band {i}: slot_base {base} does not pack contiguously (expected {cursor}); '
            'bands must tile the front of the blob from slot 0')
        assert base + n <= len(tiles), (
            f'band {i}: slots {base}..{base + n} exceed the {len(tiles)}-tile static blob')
        phase0 = a['phases'][0]
        assert phase0 == tiles[base:base + n], (
            f"band {i}: phases[0] != tiles[{base}:{base + n}]. The band's rest state must BE "
            'the static tiles it covers. This means anims and tiles came from different '
            'generator runs — regenerating layout/tiles while retaining anims produces a '
            'clean bake that ships CORRUPT art. Regenerate both together (tools/forest_bg_gen.py).')
        cursor += n


def main():
    with open(OVERRIDE) as f:
        data = json.load(f)
    layout, tiles = data['layout'], data['tiles']

    # ---- HCZ-pillar tile-band animation, table-driven (up to 4 bands).
    # Each band's phase-0 tiles occupy a contiguous slot range starting at
    # slot_base (bands packed from slot 0, in list order), column-major so
    # whole-column rotation is two wrapped DMAs. Emit one concatenated banks
    # bin + a pure-data band table (engine reads it at runtime — act data
    # assembles after engine code, so no assemble-time conditionals).
    DRIVERS = {'camera_x': 0, 'camera_y': 1, 'timer': 2}
    anims = data.get('anims')
    if anims is None and data.get('anim'):
        anims = [data['anim']]                  # legacy single-band shape
    if anims:
        validate_band_coherence(anims, tiles)
        assert len(anims) <= BGANIM_MAX_BANDS, (
            f'{len(anims)} animated bands authored but the engine sizes BgAnim_LastStep '
            f'for at most BGANIM_MAX_BANDS={BGANIM_MAX_BANDS}. Raising it here is NOT '
            f'enough: engine/system/constants.emp (which sizes the array) and '
            f'engine/level/bg_anim.emp (which bounds the runtime assert) hold the same '
            f'number and must be raised together, or BgAnim_Update walks past the array '
            f'in the release shape. See BGANIM_MAX_BANDS at the head of this file.')
        banks = bytearray()
        bands = []
        slot_cursor = 0
        for a in anims:
            cols, rows = a['cols'], a['rows']
            n = cols * rows
            pattern_px = a['pattern_px']
            col_bytes = rows * 32
            col_shift = col_bytes.bit_length() - 1
            assert (1 << col_shift) == col_bytes, 'column bytes must be a power of 2'
            assert pattern_px == cols * 8, 'pattern width must equal cols*8'
            slot_base = a.get('slot_base', slot_cursor)
            assert slot_base == slot_cursor, 'bands must pack contiguously from slot 0'
            slot_cursor += n
            strip_off = len(banks)
            for bank in a['phases']:
                assert len(bank) == n
                for t in bank:
                    for row in range(8):
                        for col in range(4):
                            hi = t[row*8 + col*2] & 0xF
                            lo = t[row*8 + col*2 + 1] & 0xF
                            banks.append((hi << 4) | lo)
            bands.append({
                'driver': DRIVERS[a.get('driver', 'camera_x')],
                'driver_name': a.get('driver', 'camera_x'),
                'rate_shift': a.get('rate_shift', 2),
                'step_mask': pattern_px - 1,
                'col_shift': col_shift,
                'tile_count': n,
                'slot_base': slot_base,
                'bank_offsets': [strip_off + ph * n * 32 for ph in range(len(a['phases']))],
            })
        with open(os.path.join(OUT_DIR, 'bg_anim_banks.bin'), 'wb') as f:
            f.write(banks)
        # Parcel K3 run B: BgAnim_Table is a natively-placed `.emp` section
        # (ojz_bg_anim). Per band, a 44-byte record contiguous in the section:
        # 6 u16 header words (baked constants; BG_TILE_BASE_VRAM = $8000) then an
        # 8-entry pointer array `extern("BgAnim_Banks") + off` (link-relative,
        # resolved at link). Mirrors engine/level/bg_anim.emp `struct bganim_band`
        # field-for-field (the LOCKSTEP contract).
        #
        # THE `extern(...)` IS LOAD-BEARING AND WAS WRONG UNTIL 2026-08-24. This arm
        # shipped booked as "FORMAT-FAITHFUL BUT NOT BYTE-PROVEN" — no act in the tree
        # authored BG animation, so the six-target gate only ever exercised the stub
        # below, and the array went out as a bare `BgAnim_Banks + off`. The first real
        # band discharged the booking: sigil resolves bare names against the compiler's
        # name table, which these generated act modules are not in, and answered
        # `[Error] unknown name \`BgAnim_Banks\`` once per entry (16 on the two-band
        # b0e5a661 fixture). extern("Name") is the accepted spelling for a link-time
        # symbol inside an emitted data image; sec_local_maps.emp in the same generated
        # directory is the precedent. THE ADDEND FORM WORKS — `extern("X") + N` links
        # (measured here, not inherited); docs/EMP_PITFALLS.md §5's warning about
        # extern() poisoning comptime-ness applies to images a comptime pin then
        # COMPARES, and nothing pins this one.
        #
        # The arm now has a test that runs it: tools/test_bg_emit.py::TestBgAnimEmission
        # drives this emitter over the real two-band fixture and rejects any bare
        # link-time symbol in an emitted array initializer.
        # (docs/superpowers/notes/2026-08-01-k3-run-b.md §animated-arm;
        #  docs/DEFERRED_WORK.md "the first real authored band does not assemble".)
        BG_TILE_BASE_VRAM = 0x8000
        for b in bands:
            assert len(b['bank_offsets']) == 8, \
                'bganim_band.banks is [*u8; 8]: each band needs exactly 8 phases'
        with open(os.path.join(OUT_DIR, 'bg_anim.emp'), 'w') as f:
            f.write('// AUTO-GENERATED by tools/inject_editor_bg.py — DO NOT EDIT.\n')
            f.write('// OJZ Act 1 BG tile-band animation table (HCZ-pillar technique).\n')
            f.write('// Mirrors engine/level/bg_anim.emp `struct bganim_band` (LOCKSTEP).\n')
            f.write('// Natively placed at the ojz_bg_anim section.\n')
            f.write('module games.sonic4.ojz_bg_anim_act1 in ojz_bg_anim\n\n')
            f.write(f'pub data BgAnim_Table: u16 = {len(bands)}   // band count\n')
            for i, b in enumerate(bands):
                vram_dest = BG_TILE_BASE_VRAM + b['slot_base'] * 32
                f.write(f'// band {i}: {b["tile_count"]} tiles at BG slot {b["slot_base"]}, '
                        f'driver {b["driver_name"]}, 1px per {1 << b["rate_shift"]} units\n')
                f.write(f'data _BgAnim_Band{i}_hdr: [u16; 6] = '
                        f'[{b["driver"]}, {b["rate_shift"]}, {b["step_mask"]}, '
                        f'{b["col_shift"]}, {b["tile_count"]}, ${vram_dest:X}]\n')
                # extern("BgAnim_Banks"), NOT a bare `BgAnim_Banks` — see the
                # spelling note at :151. tools/test_bg_emit.py::TestBgAnimEmission
                # is the gate on this line.
                banks_list = ', '.join(f'extern("BgAnim_Banks") + {off}'
                                       for off in b['bank_offsets'])
                f.write(f'data _BgAnim_Band{i}_banks: [*u8; 8] = [{banks_list}]\n')
            f.write('pub data BgAnim_Banks = '
                    'embed("games/sonic4/data/generated/ojz/act1/bg_anim_banks.bin")\n')
        print(f'[inject_editor_bg] anim: {len(bands)} band(s), {len(banks)} bytes of banks')
    else:
        # no animation: emit the disabled stub as a natively-placed `.emp` section
        # (Parcel K3 run B). band_count = 0 disables the whole system.
        with open(os.path.join(OUT_DIR, 'bg_anim.emp'), 'w') as f:
            f.write('// AUTO-GENERATED by tools/inject_editor_bg.py — DO NOT EDIT.\n')
            f.write('// OJZ Act 1 BG tile-band animation table (HCZ-pillar technique).\n')
            f.write('// The engine contract (engine/level/bg_anim.emp, BgAnim_Update):\n')
            f.write('// every act supplies BgAnim_Table; band_count = 0 disables the whole\n')
            f.write('// system. This act has no BG animation, so it is the disabled stub.\n')
            f.write('// Natively placed at the ojz_bg_anim section.\n')
            f.write('module games.sonic4.ojz_bg_anim_act1 in ojz_bg_anim\n\n')
            f.write('pub data BgAnim_Table: u16 = 0              // band_count = 0 (disabled)\n')
            f.write('pub data BgAnim_Banks = Data.empty         // bank-blob base (empty in the stub)\n')
        print('[inject_editor_bg] anim: disabled stub (band_count = 0)')
    if len(layout) == 2048:
        layout = layout + [0]*2048          # legacy 32-row layout: pad to 64 rows
    assert len(layout) == 4096, f'layout must be 64x32 or 64x64 words, got {len(layout)}'
    assert len(tiles) <= BG_TILE_CAPACITY, f'{len(tiles)} tiles exceeds BG capacity {BG_TILE_CAPACITY}'

    # nametable: local -> VRAM-absolute indices, preserving pal/pri/flip bits.
    # This is the editor->engine boundary: the editor layout is ROW-MAJOR
    # (idx = row*64 + col), the engine reads COLUMN-MAJOR (blob[col*128 + row*2]
    # — column-contiguous, 64 rows per column). Transpose here so every engine
    # consumer (BG_Init, Section_RedrawPlanes' Plane B blit, Draw_BG_TileColumn)
    # gathers a column with sequential reads. See engine/level/bg.emp header.
    COLS, ROWS = 64, 64
    nt = bytearray(COLS * ROWS * 2)
    for col in range(COLS):
        for row in range(ROWS):
            word = layout[row * COLS + col]
            if word != 0:
                idx = word & 0x7FF
                word = (word & ~0x7FF) | ((idx + BG_TILE_BASE_SLOT) & 0x7FF)
            struct.pack_into('>H', nt, (col * ROWS + row) * 2, word)
    with open(os.path.join(OUT_DIR, 'zone_bg.bin'), 'wb') as f:
        f.write(nt)

    # tile blob: BE byte-length header + raw 4bpp tiles
    blob = bytearray()
    for t in tiles:
        for row in range(8):
            for col in range(4):
                hi = t[row*8 + col*2] & 0xF
                lo = t[row*8 + col*2 + 1] & 0xF
                blob.append((hi << 4) | lo)
    # Tier-1 move.l blit contract (BG_Init .tile_copy): the runtime copies the
    # tile body a longword at a time, so the byte length must be a multiple of 4.
    # Tiles are 32 bytes each, so this holds by construction; assert it anyway so
    # a format change can never feed the move.l loop a sub-longword remainder.
    assert len(blob) % 4 == 0, f'BG tile blob must be 4-byte granular for move.l, got {len(blob)}'
    with open(os.path.join(OUT_DIR, 'bg_tiles.bin'), 'wb') as f:
        f.write(struct.pack('>H', len(blob)))
        f.write(blob)
    print(f'[inject_editor_bg] wrote zone_bg.bin ({len(nt)}B) + bg_tiles.bin ({len(tiles)} tiles)')

    # optional: stamp a BG palette line. strip_gen copies ojz_palette.bin from
    # sonic_hack every build, so a palette that matches the injected art must be
    # written HERE (inject runs after strip_gen) or the colours revert.
    if 'palette' in data:
        cram_line = int(data.get('palette_line', 2)) & 3
        words = data['palette']
        assert len(words) == 16, f'palette must be 16 CRAM words, got {len(words)}'
        # ojz_palette.bin's 3 source lines load starting at CRAM line 1 (the
        # scroll test / act loader put OJZ_Palette at Palette_Buffer+$20), so
        # source line = cram_line - 1. The BG nametable references CRAM line 2.
        file_line = cram_line - 1
        assert file_line >= 0, 'BG palette maps to CRAM line >=1'
        pal_path = os.path.join(OUT_DIR, 'ojz_palette.bin')
        pal = bytearray(open(pal_path, 'rb').read())
        for i, w in enumerate(words):
            struct.pack_into('>H', pal, file_line * 32 + i * 2, w & 0xFFFF)
        with open(pal_path, 'wb') as f:
            f.write(pal)
        print(f'[inject_editor_bg] stamped CRAM line {cram_line} (file line {file_line}, {len(words)} colours)')

if __name__ == '__main__':
    main()
