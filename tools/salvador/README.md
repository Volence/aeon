# salvador (vendored)

ZX0 packer by Emmanuel Marty, vendored for the s4_engine build pipeline.

- Origin: https://github.com/emmanuel-marty/salvador
- Version: v1.4.2
- Trimmed to what `make` needs: `Makefile`, `src/` (including the
  libdivsufsort sources it links), and the license files. VS2019 project,
  bundled decompressor asm, and libdivsufsort CMake scaffolding removed.

Licenses (all retained in this directory):
- salvador itself: Zlib (`LICENSE.zlib.md`)
- `src/matchfinder.c`: CC0 (`LICENSE.cc0.md`)
- `src/libdivsufsort/`: MIT (`src/libdivsufsort/LICENSE`)

The engine uses the default **modern (V2)** ZX0 format — it matches the
vendored 68000 decompressor (`engine/zx0_decompress.asm`, adapted from
unzx0_68000.S in this same project). Do not pass `-classic`.

build.sh compiles this once into `tools/bin/salvador` if the binary is
missing (`make -C tools/salvador`).
