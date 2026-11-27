# Sonic Pocket Adventure in C, on every platform: the plan

Sonic Pocket Adventure (Neo Geo Pocket Color, 1999-2000) decompiled to C that does what the original does, checked
frame by frame against MAME's cores, and ported with SDL 3 to every platform the other ports have. Started
26-11-2026 from Valley Bell's disassembly (2014-2016, released 2023:
<https://forums.sonicretro.org/threads/sonic-pocket-adventure-disassembly-and-tools.42039/>).

## Decided (Sebas, 26-11-2026)

- The C version, as the other decompilations (the kit, the descompilado-prolijo standard), not an emulator.
- The port with SDL 3, on every platform; **64-bit executables only** (x64, arm64: no armeabi-v7a, so Android Go
  phones with a 32-bit system are left out).
- **The resource bar is an ESP32-class machine** (and a thin client, a low-end phone, a Raspberry Pi 3), designed for
  from the first build: the console's state in fixed small RAM, no allocation per frame, assets read in place in their
  2-bit format, video a line at a time, no threads and no stack switching, integers only.
- **Nothing of the NGP in arcade-decomp**: the TLCS-900H frontend (`tlcs900/`) and the console (`ngp/`) go in
  console-decomp; arcade-decomp gives only the core without a CPU (the decompiler), as for Spinball.
- **Game Gear: phase 2**, after the C and the port: a demake with the C as its specification, its ROM built by a tool
  from the player's NGPC ROM, never distributed.

## What is here

| Path | What |
|---|---|
| `rom/sonic.ngc`, `rom/ngpcbios.rom` | the cartridge and the NGPC BIOS (the BIOS for the reference only) |
| `external/spa-disassembly/` | Valley Bell's release, extracted (the download, its 7z: `D:\vs-cheviman\spa-port`) |
| `build/asm/` | `external/spa-disassembly/disassembly` assembled with its `asw` (0 errors): `built.npc`, `Main.lst` (address and bytes of every line) |
| `tools/console/`, branch `ngp` | MAME 0.289's sources, all BSD-3-Clause, in `tlcs900/mame/` (core, 900 and 900/H tables, disassembler, TMP95C061) and `ngp/reference/mame/` (ngp.cpp, K1GE/K2GE, T6W28); `external/mame/ngpc.xml` (ignored by git) |

`rom/`, `external/` and `build/` are ignored by git.

## What the first round found

- **The ROM**: `rom/sonic.ngc` is CRC 8bd22145; MAME's `sonic` (CRC 356f0849, SHA-1 3fe15d43...) is the same with the
  flash's save area (3F8000-3FBFFF, 16 KB) holding the disassembly's default save instead of FF: with that block put
  in, the SHA-1 is MAME's. The program is the same: the first run accepts both.
- **The labels hold**: against `build/asm/built.npc`, outside that area, only 5 `LD (mem),(mem)` differ (AS's other
  encoding, the same length: 23E196 twice, 291C27, 39C75B, 39C761). The 8855 labels are the original's addresses:
  they go to `symbols.txt` as they are.
- **The BIOS**: `rom/ngpcbios.rom` is MAME's `ngpcbios.rom` (CRC 6eeb6f40, SHA-1 edc13192...); No-Intro names it
  "[BIOS] SNK Neo Geo Pocket (Japan, Europe) (En,Ja).ngp". The game calls it 5 times (SWI 1): VECT_SHUTDOWN,
  VECT_CLOCKGEARSET, VECT_RTCGET, VECT_FLASHWRITE and debug call 0F0h; and it reads what the BIOS leaves in RAM
  (6C00-6FFF: `NgpOSMode`, 6F83, the pad at 6F82...).
- **One frame wait**: `MainLoop` calls each object of a circular list; only the global object waits, in
  `WaitSomeFrames`, called from one place. The frame can end there and return to the port's loop: no tasks.
- **The hardware it uses**: timers 0 and 1, the watchdog, the interrupt levels; micro DMA only cleared
  (`SYS_PATCH`); the PSG, DACs, pad, power button, link, Z80; the whole K2GE in colour mode; the flash by the BIOS and
  by its own commands (3F21xx). The detail: console-decomp `ngp/docs/hardware.md`.
- **Sound**: its own Z80 driver, loaded into the Z80's RAM; Valley Bell's hand C port (`external/spa-disassembly/sound-driver/spa_drv.c`)
  gives the names. arcade-decomp's Z80 frontend decompiles it.

## What the second round found (`ngpref`, 26-11-2026)

- **MAME's sources build unchanged**: the TLCS-900/H core, the TMP95C061 and dasm900 on a stand-in for MAME's
  emu.h (console-decomp `tlcs900/stub`: PAIR, the devcb callbacks, the TMP95C061's internal registers as an
  address map the host reads its table from), the K2GE on another (`ngp/reference/video/stub`: timers the host
  fires, the screen's beam from the host's present, MAME's indirect palette), the Z80 and the T6W28 on
  arcade-decomp's sound stand-in (`konami/reference/sound/emu.h`). ngp.cpp's flash commands are copied as they
  are (`flash.hxx`); the rest of the driver (the memory map, the I/O, the Z80's lines, the clock, the NVRAM) is
  `ngpref.cpp`, and a review of it against ngp.cpp found no difference.
- **A console never set up turns itself off**: with no NVRAM the BIOS fills its RAM, sets the clock to 1998 and
  jumps to its power off (FF1074): a white screen, then HALT at FF1127 with the power button's NMI enabled (I/O
  B3 bit 2). MAME's power_callback raises the NMI when the button is let go; then the BIOS asks for its first
  setup (the language, the colours for monochrome software, the date and time: Jan. 1, 1999 0:00 AM).
- **The NVRAM holds the settings only after a power off**: saved with the game running, the BIOS asks for its
  setup again; saved after the power button turned the console off (the BIOS writes A5A5 at 6C7A and 4E50 at
  6E95 on its way), the BIOS starts again at FF1800 (MAME's machine_reset with the NVRAM loaded) and goes
  straight to its logo. `tests/controls/setup.txt` writes it (`--save-nvram build/setup.nv`); the scenarios
  start from it.
- **The path to the game**: the NEOGEO POCKET logo, SEGA (frame 525 from the NVRAM), the game's intro and title
  (1125), PRESS "A" BUTTON (1350), the menu (START, GO TO ROOM), Neo South Island act 1 (1640):
  `tests/controls/neo_south_island.txt`, 3000 frames in about 5 seconds. Two runs give the same hashes of the
  state, the picture and the sound in every frame.
- **The game writes its flash at once**: 26084 writes of the cartridge's space while it starts (its own command
  sequences at 3F21xx: the save area set up).
- **Left for the next round**: `--jumps` and `--rom-reads` (the core reads its instructions through RDMEM, as
  its data: its RDOP must mark them, a change to MAME's tlcs900.cpp to say in its header); the sound side
  (`ngpsound.cpp`, a draft of the local worker) passes 21 of the 26 checks of its test (`test_ngpsound.cpp`,
  beside it), and the five that fail (two
  runs' hashes, the TMP95C061's writes to the T6W28, the DACs) are being fixed; the scheduling differs from
  MAME's in one place, said in ngpref.cpp's header: the Z80 is brought up to the present before every write of
  the TMP95C061 to the sound side, not only before a change of its lines.

## The steps, each with its check

1. **Repositories**: `spa-decomp` (tools/core = arcade-decomp, tools/console = console-decomp on `ngp`) and
   `spa-port`, as TMNT. Check: the submodules at their commits, `rom/` ignored. Done 26-11-2026 for spa-decomp (no commit yet).
2. **`ngpref`** (console-decomp `ngp/reference/`): MAME's TMP95C061 core, MAME's Z80 and T6W28, and MAME's K2GE
   adapted to run without MAME's device framework, against the runtime's console; the real BIOS. Check: from a
   controls script it boots the BIOS, the SEGA screen, the title and a zone; BMP frames and hashes per frame (state,
   picture, sound); `--trace`, `--jumps`, `--rom-reads`. Done 26-11-2026 but for `--jumps`, `--rom-reads` and the
   sound side's last five checks (above); the console is ngp.cpp's in `ngpref.cpp` until the runtime's (step 3).
3. **The runtime's console** (`ngp/runtime/`, the resource bar above): memory, TMP95C061 timers and interrupts,
   K2GE a line at a time, T6W28 and DACs, flash, pad; and **the BIOS in C** (boot, the RAM it leaves, the vectors, the
   5 calls). Check: `ngpref` with the runtime's K2GE gives MAME's K2GE picture; with the BIOS in C, the same hashes as
   with the real one.
4. **Scenarios**: attract, every zone and act, the special stages, the bosses, options, the debug menu, a save.
   Check: the share of instructions run, and what never runs, written down.
5. **The TLCS-900H decoder** (console-decomp `tlcs900/`). Check: the same as MAME's `dasm900` at every offset of the
   program and of an image of every opcode.
6. **Coverage and named data**: `symbols.txt` from the disassembly's labels and comments; the asset cut from its
   `binclude` files. Check: 0 bytes unexplained; each extractor `--check` byte for byte.
7. **The 1:1 translator and the decompiler** (on arcade-decomp's core). Check: the same hashes as `ngpref` in every
   frame of every scenario; then the noise report, 0 reads of the ROM.
8. **The port** (SDL 3, the minimum of ports-dispositivos, 64-bit only). Check: that minimum, and the resource bar
   measured (RAM, time per frame with SDL's software renderer forced).
