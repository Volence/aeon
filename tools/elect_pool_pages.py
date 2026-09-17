#!/usr/bin/env python3
"""elect_pool_pages.py — per-page ZX0/raw form election for an act art pool, and
the `.emp` section that embeds the elected blobs plus the manifest v2 table.

WHY THIS FILE EXISTS. This was thirty lines of bash inside tools/regenerate-level.sh,
which is the ONE act's re-bake. The S2-COMPRESSED-ACT clip bake
(tools/clip_rom_bake.py, staged plan row 6) has to produce the same artifacts for a
clip act, and a second copy of a byte-exact emitter is how two trees end up
disagreeing about a wrapper header nobody looks at. So the election moved here and
regenerate-level.sh CALLS it. Byte-neutrality for the shipped act is not asserted:
the re-bake is re-run and `git status games/sonic4/data` must stay clean (the
landing evidence records that run).

WHAT AN ELECTION IS. The strip generator emits the globally-deduped act art pool
split into fixed-size pages of ART_POOL_PAGE_TILES tiles = ART_POOL_PAGE_BYTES each,
plus a JSON sidecar (ojz_act_pool_manifest.json) carrying per-page {tiles, pinned}.
Each page then gets a storage FORM:

  ZX0 (form 0): [u16 BE uncompressed size][u8 flags=0][u8 version=2] wrapper +
                salvador (modern/V2) stream — staged decode. Kept only when
                zx0 * RAW_ELECT_DEN <= raw * RAW_ELECT_NUM (>= 10% saving vs raw).
  raw (form 1): the uncompressed payload, NO wrapper — DMA straight from ROM.

The loader dispatches on the manifest form byte, not on the wrapper version.

TWO RULES THAT LOOK COSMETIC AND ARE NOT:

  * Pages are addressed by NUMERIC index, never by glob — a glob puts page10 before
    page2, and stale leftovers from a previously larger pool would be compressed and
    bundled.
  * Every elected blob is PADDED to EVEN length (one dead byte past the ZX0 end
    marker, never read) so every successor symbol stays word-aligned. An odd blob
    once landed OJZ_Act_Pool_PageTable at an odd address -> boot AddressError
    (2026-08-12); sigil does not auto-align data decls and an (align: 2) attr
    materializes a synthetic section the map contract then rejects.

A page bigger than one VRAM page (ART_POOL_PAGE_BYTES) is a GENERATOR bug and is
refused here rather than shipped: the loader DMAs a page into one frame.
"""

import argparse
import json
import os
import subprocess
import sys

REPO = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))

# keep .zx0 iff zx0 * DEN <= raw * NUM  (>= 10% saving)
RAW_ELECT_NUM = 9
RAW_ELECT_DEN = 10

FORM_ZX0 = 0
FORM_RAW = 1


class ElectError(Exception):
    """A refusal. Nothing partial is left behind by the caller's standards."""


def _page_count_from_manifest(manifest_path: str) -> int:
    """OJZ_ACT_POOL_PAGES out of the generated `.emp` manifest.

    Parsed rather than recomputed from the sidecar, exactly as the bash did, so the
    two generated files must agree or this refuses — they are written by the same
    pass and a disagreement means one of them is stale.
    """
    prefixes = ("pub const OJZ_ACT_POOL_PAGES = ", "const OJZ_ACT_POOL_PAGES = ")
    try:
        with open(manifest_path, "r") as fh:
            for line in fh:
                line = line.rstrip("\n")
                for p in prefixes:
                    if line.startswith(p):
                        return int(line[len(p):])
    except OSError as exc:
        raise ElectError(f"could not read {manifest_path}: {exc}") from exc
    raise ElectError(f"could not read OJZ_ACT_POOL_PAGES from {manifest_path}.")


def elect(pool_dir: str, page_bytes: int, salvador: str,
          module: str, section: str, symbol_prefix: str,
          table_symbol: str, emp_name: str, embed_prefix: str,
          log=print) -> dict:
    """Elect a form for every page of `pool_dir` and write the `.emp` section.

    `embed_prefix` is the path each embed() names, relative to the repo root — the
    build resolves embeds from there, so it is NOT derived from `pool_dir`'s
    absolute spelling.

    Returns {"pages": n, "forms": [...], "zx0": n0, "raw": n1, "bytes": total}.
    """
    manifest_emp = os.path.join(pool_dir, "ojz_act_pool_manifest.emp")
    sidecar = os.path.join(pool_dir, "ojz_act_pool_manifest.json")
    pages = _page_count_from_manifest(manifest_emp)
    if not os.path.isfile(sidecar):
        raise ElectError(
            f"manifest v2 sidecar {sidecar} missing (run the strip generator first).")
    with open(sidecar, "r") as fh:
        meta = json.load(fh)["pages"]
    if len(meta) != pages:
        raise ElectError(
            f"sidecar has {len(meta)} pages, manifest declares {pages}.")

    # Stale elected blobs from a previously LARGER pool would otherwise be embedded.
    for name in os.listdir(pool_dir):
        if name.startswith("act_pool_page") and name.endswith((".zx0", ".zx0.tmp", ".raw")):
            os.remove(os.path.join(pool_dir, name))

    forms, exts, total = [], [], 0
    for k in range(pages):
        page_bin = os.path.join(pool_dir, f"act_pool_page{k}.bin")
        if not os.path.isfile(page_bin):
            raise ElectError(
                f"{page_bin} missing but the manifest declares {pages} pages.")
        size = os.path.getsize(page_bin)
        if size > page_bytes:
            raise ElectError(
                f"{page_bin} is {size} B — exceeds one page ({page_bytes}).")
        tmp = page_bin[:-4] + ".zx0.tmp"
        try:
            subprocess.run([salvador, page_bin, tmp], check=True,
                           stdout=subprocess.DEVNULL)
            zstream = os.path.getsize(tmp)
            zsize = zstream + 4                      # + 4-byte wrapper
            if zsize * RAW_ELECT_DEN <= size * RAW_ELECT_NUM:
                out = page_bin[:-4] + ".zx0"
                with open(out, "wb") as fh, open(tmp, "rb") as src:
                    fh.write(bytes([(size >> 8) & 0xFF, size & 0xFF, 0x00, 0x02]))
                    fh.write(src.read())
                forms.append(FORM_ZX0)
                exts.append("zx0")
            else:
                out = page_bin[:-4] + ".raw"
                with open(out, "wb") as fh, open(page_bin, "rb") as src:
                    fh.write(src.read())
                forms.append(FORM_RAW)
                exts.append("raw")
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
        if os.path.getsize(out) % 2 == 1:
            with open(out, "ab") as fh:
                fh.write(b"\x00")
        total += os.path.getsize(out)

    emp_path = os.path.join(pool_dir, emp_name)
    with open(emp_path, "w") as fh:
        fh.write("// AUTO-GENERATED by tools/elect_pool_pages.py (tools/regenerate-level.sh\n")
        fh.write("// for the shipped act, tools/clip_rom_bake.py for a clip act) — DO NOT EDIT.\n")
        fh.write("// OJZ Act 1 act-wide paged art pool: per-page ZX0/raw blob embeds + the\n")
        fh.write("// manifest v2 table [PageManifest;N] the loader strides by page number\n")
        fh.write("// ({source, tiles, form, flags}). Natively placed at the ojz_act_pool section;\n")
        fh.write("// consumed by act_descriptor.emp (OJZ_Act_Pool_PageTable). Page blobs are\n")
        fh.write("// PADDED to even length at generation (one dead byte past the ZX0 end\n")
        fh.write("// marker) — an odd blob once landed the table at an odd address -> boot\n")
        fh.write("// AddressError (2026-08-12). sigil does not auto-align data decls.\n")
        fh.write(f"module {module} in {section}\n")
        fh.write("\n")
        fh.write("use engine.structs.{PageManifest}\n")
        fh.write("\n")
        for k in range(pages):
            fh.write(f'pub data {symbol_prefix}{k} = '
                     f'embed("{embed_prefix}/act_pool_page{k}.{exts[k]}")\n')
        fh.write("\n")
        fh.write(f"pub data {table_symbol}: [PageManifest; {pages}] = [\n")
        for k in range(pages):
            fh.write(f'  PageManifest{{ pm_source: extern("{symbol_prefix}{k}"), '
                     f'pm_tiles: {meta[k]["tiles"]}, pm_form: {forms[k]}, '
                     f'pm_flags: {1 if meta[k]["pinned"] else 0} }},\n')
        fh.write("]\n")

    n0 = forms.count(FORM_ZX0)
    if log:
        log(f"elect_pool_pages: {pages} page(s) — {n0} ZX0, {pages - n0} raw, "
            f"{total} B elected -> {os.path.relpath(emp_path, REPO)}")
    return {"pages": pages, "forms": forms, "zx0": n0, "raw": pages - n0,
            "bytes": total, "emp": emp_path}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pool-dir", required=True,
                    help="the generated act directory holding act_pool_page*.bin")
    ap.add_argument("--page-bytes", type=int, required=True,
                    help="ART_POOL_PAGE_BYTES, read from the engine by the caller")
    ap.add_argument("--salvador", default=os.path.join(REPO, "tools", "bin", "salvador"))
    ap.add_argument("--module", default="games.sonic4.ojz_act_pool_act1")
    ap.add_argument("--section", default="ojz_act_pool")
    ap.add_argument("--symbol-prefix", default="OJZ_Act_Pool_Page")
    ap.add_argument("--table-symbol", default="OJZ_Act_Pool_PageTable")
    ap.add_argument("--emp-name", default="ojz_act_pool.emp")
    ap.add_argument("--embed-prefix", default="games/sonic4/data/generated/ojz/act1")
    args = ap.parse_args(argv)
    try:
        elect(args.pool_dir, args.page_bytes, args.salvador, args.module,
              args.section, args.symbol_prefix, args.table_symbol,
              args.emp_name, args.embed_prefix)
    except ElectError as exc:
        print(f"elect_pool_pages: REFUSED — {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
