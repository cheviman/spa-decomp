# Sonic Pocket Adventure — decompilation

A decompilation of Sega's 1999 Neo Geo Pocket Color game *Sonic the Hedgehog Pocket Adventure* (a TLCS-900/H
program, with a Z80 running its own sound driver) into readable C that does exactly what the original does,
checked frame by frame against MAME's cores.

**This repository contains no game data.** You bring your own cartridge dump (and, for the reference tool only,
the console's BIOS); the tools check them, and everything they take from them stays on your computer.

Work in progress: just started (`docs/plan.md`).

## Status

As of 2026-11-28:

- [x] Cartridge verification: the World release, CRC32 356f0849 (MAME's `sonic`) or 8bd22145 (the same with its
      save area erased)
- [x] The disassembly's labels checked against the original: the same addresses (`docs/plan.md`)
- [x] Reference: the original program and the console's BIOS on MAME's TMP95C061 (TLCS-900/H) core, with MAME's
      Z80, T6W28 and K2GE ([console-decomp](https://github.com/cheviman/console-decomp)'s `ngpref`), from the
      BIOS's first setup to the title and Neo South Island (`tests/controls/`)
- [x] `ngpref --jumps` and `--rom-reads`: where each JP or CALL through a register went, and the cartridge's
      bytes read as data, under the instruction that read them
- [x] The runtime's K2GE (console-decomp's, in C, a line at a time): the same pens as MAME's in every line of
      both scenarios
- [x] The runtime's board (console-decomp's, in C: memory, I/O, clock, pad, flash, NVRAM, the cartridge read in
      place): the reference runs on it with the same hashes, and its flash matches MAME's on random commands
- [x] The runtime's K2GE registers and timing, T6W28 and TMP95C061 devices (timers, interrupts, micro DMA,
      A/D), each run beside MAME's in the reference with no difference in either scenario, and each against
      MAME's on random operations
- [x] The sound's mix: MAME's DACs and the speaker's sum in integers, the same as MAME's in every value of
      both scenarios and on every T6W28 value with every DAC byte
- [x] What the program takes from the BIOS (`ngpref --handover`): the bytes it reads of what the BIOS left at the
      hand-over, the BIOS's routines it goes on using, and the registers the BIOS set
- [x] The BIOS's boot in C (console-decomp's `ngp/bios.h`): put in place of the BIOS at the hand-over
      (`ngpref --boot`), the console it leaves is the BIOS's in every register and byte the program reads, and
      the pictures, the sound and the program's bus are the same in every frame of both scenarios
- [x] The scenarios (`tests/controls`, 54): the attract, the debug menu, the endings, every zone and act, every
      act's star posts and one object of each kind in each act (`tools/object_scenarios.py`), every boss beaten and
      its act ended, the special stage from an act's ring, the rooms (a time trial to its signpost and the ranking,
      duel, puzzle, options), the true ending by play to its credits: 73.64% of the program's instructions run
      (`tools/listing_coverage.py`), what never runs (mostly the link's screens) written down in `docs/plan.md`
- [x] The TLCS-900/H decoder (console-decomp's `tlcs900/disassembler.py`): MAME's text and length at every offset of
      the cartridge, of the BIOS and of an image of every opcode, with each instruction's operands and flow
- [x] Every byte of the cartridge a line of the disassembly (`tools/listing_map.py`): `symbols.txt` (functions,
      labels, the registers and RAMs by name, Valley Bell's comments) and `assets.txt`, the 2942 binary files
- [x] The binary files cut from your dump (`tools/extract_assets.py`): tile sets as PNG and tile maps as text,
      each built back to the cartridge's bytes by `--check`
- [x] The sprites, palettes, levels and the SEGA voice in editable forms (`tools/forms/`): each sprite as text and
      a picture, the palettes, block layouts, block maps and collision as words, the object layouts by screen, the
      tile data with no count as PNG, the voice as a WAV, all built back by `--check`
- [ ] The rest of the named data in editable forms: the songs and effects, the objects' paths, the scripts
- [ ] The translated program, then the decompiled C, the same as the reference in every frame

## Layout

- `tools/core/`: [arcade-decomp](https://github.com/cheviman/arcade-decomp), the decompiler's core (submodule)
- `tools/forms/`: the text and WAV forms of the cartridge's data (sprites, words, object layouts, the voice)
- `tools/console/`: [console-decomp](https://github.com/cheviman/console-decomp), the TLCS-900/H and the Neo Geo
  Pocket Color (submodule)
- `runtime/`: the reader of your cartridge and BIOS (`rom_set.c`), for the tools that run the original code
- `tests/controls/`: the scenarios, controls scripts for `ngpref` (format in console-decomp's `ngp/script.h`)
- `symbols.txt`, `assets.txt`: the program's names and the binary files' places (addresses only, no game data)
- `assets/`: the binary files cut from your dump by `tools/extract_assets.py` (ignored by git)
- `rom/`: your dumps (ignored by git)
- `external/`: other people's work read for reference (ignored by git)

## Building and running

With `rom/sonic.ngc` and `rom/ngpcbios.rom` in place (any name: they are known by their CRC32), CMake 3.20, a
C++20 compiler and Python 3:

    cmake -S . -B build/msvc
    cmake --build build/msvc --config Release --target ngpref
    build/bin/ngpref --script tests/controls/setup.txt --save-nvram build/setup.nv
    build/bin/ngpref --nvram build/setup.nv --script tests/controls/neo_south_island.txt --video-dump 1700 --video-dir build

The first run sets the console up as a new one is (its BIOS asks once) and keeps its NVRAM; the second plays to
Neo South Island and writes frame 1700 as `build/frame_1700.bmp`. `ngpref --help` lists the rest.

    py tools/extract_assets.py
    py tools/extract_assets.py --check

cut the cartridge's binary files into `assets/` (tile sets as PNG; maps, sprites, palettes, block layouts and
object layouts as text; the SEGA voice as WAV; the rest as they are) and build them back, byte for byte.

## Thanks

Valley Bell's disassembly and research (2014-2016, released 2023:
[Sonic Retro](https://forums.sonicretro.org/threads/sonic-pocket-adventure-disassembly-and-tools.42039/)) give this
decompilation its names, its comments and the cut of the data.

## License

The code of this repository is BSD 3-Clause (`LICENSE`). Sonic the Hedgehog and the game belong to Sega; the
Neo Geo Pocket Color and its BIOS to SNK.
