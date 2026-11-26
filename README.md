# Sonic Pocket Adventure — decompilation

A decompilation of Sega's 1999 Neo Geo Pocket Color game *Sonic the Hedgehog Pocket Adventure* (a TLCS-900/H
program, with a Z80 running its own sound driver) into readable C that does exactly what the original does,
checked frame by frame against MAME's cores.

**This repository contains no game data.** You bring your own cartridge dump (and, for the reference tool only,
the console's BIOS); the tools check them, and everything they take from them stays on your computer.

Work in progress: just started (`docs/plan.md`).

## Status

As of 2026-11-26:

- [x] Cartridge verification: the World release, CRC32 356f0849 (MAME's `sonic`) or 8bd22145 (the same with its
      save area erased)
- [x] The disassembly's labels checked against the original: the same addresses (`docs/plan.md`)
- [ ] Reference: the original program on MAME's TMP95C061 (TLCS-900/H) core, with MAME's Z80, T6W28 and K2GE,
      against the Neo Geo Pocket Color in C of [console-decomp](https://github.com/cheviman/console-decomp) (`ngpref`)
- [ ] The scenarios, the TLCS-900/H decoder, the coverage and the named data
- [ ] The translated program, then the decompiled C, the same as the reference in every frame

## Layout

- `tools/core/`: [arcade-decomp](https://github.com/cheviman/arcade-decomp), the decompiler's core (submodule)
- `tools/console/`: [console-decomp](https://github.com/cheviman/console-decomp), the TLCS-900/H and the Neo Geo
  Pocket Color (submodule)
- `rom/`: your dumps (ignored by git)
- `external/`: other people's work read for reference (ignored by git)

## Thanks

Valley Bell's disassembly and research (2014-2016, released 2023:
[Sonic Retro](https://forums.sonicretro.org/threads/sonic-pocket-adventure-disassembly-and-tools.42039/)) give this
decompilation its names, its comments and the cut of the data.

## License

The code of this repository is BSD 3-Clause (`LICENSE`). Sonic the Hedgehog and the game belong to Sega; the
Neo Geo Pocket Color and its BIOS to SNK.
