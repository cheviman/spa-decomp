# Sonic Pocket Adventure — decompilation

A decompilation of Sega's 1999 Neo Geo Pocket Color game *Sonic the Hedgehog Pocket Adventure* (a TLCS-900/H
program, with a Z80 running its own sound driver) into readable C that does exactly what the original does,
checked frame by frame against MAME's cores.

**This repository contains no game data.** You bring your own cartridge dump (and, for the reference tool only,
the console's BIOS); the tools check them, and everything they take from them stays on your computer.

Work in progress: just started (`docs/plan.md`).

## Status

As of 2026-11-27:

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
- [ ] The reference against the rest of the Neo Geo Pocket Color in C of console-decomp (the K2GE's registers,
      the TMP95C061's timers and interrupts, the sound side), and the BIOS in C
- [ ] The scenarios, the TLCS-900/H decoder, the coverage and the named data
- [ ] The translated program, then the decompiled C, the same as the reference in every frame

## Layout

- `tools/core/`: [arcade-decomp](https://github.com/cheviman/arcade-decomp), the decompiler's core (submodule)
- `tools/console/`: [console-decomp](https://github.com/cheviman/console-decomp), the TLCS-900/H and the Neo Geo
  Pocket Color (submodule)
- `runtime/`: the reader of your cartridge and BIOS (`rom_set.c`), for the tools that run the original code
- `tests/controls/`: the scenarios, controls scripts for `ngpref` (format in console-decomp's `ngp/script.h`)
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

## Thanks

Valley Bell's disassembly and research (2014-2016, released 2023:
[Sonic Retro](https://forums.sonicretro.org/threads/sonic-pocket-adventure-disassembly-and-tools.42039/)) give this
decompilation its names, its comments and the cut of the data.

## License

The code of this repository is BSD 3-Clause (`LICENSE`). Sonic the Hedgehog and the game belong to Sega; the
Neo Geo Pocket Color and its BIOS to SNK.
