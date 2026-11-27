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
- **The sound side and two things of MAME's**: `ngpsound.cpp` (a draft of the local worker, finished by hand)
  passes the 26 checks of its test (`test_ngpsound.cpp`, beside it). MAME's T6W28 takes its tones' frequencies
  from port 1 only (the Z80's 4001) and port 0 gives the right side's volumes, and MAME's io_w writes both of the
  TMP95C061's ports (0000A0, 0000A1) to port 0: the TMP95C061 alone can only change those volumes. And
  t6w28.cpp's device_start leaves port 1's registers as the memory had them, so a second run started where the
  first one's chip had been played on with its leftovers: the chips are now built in zeroed memory.
- **The scheduling differs from MAME's in one place**, said in ngpref.cpp's header: the Z80 is brought up to
  the present before every write of the TMP95C061 to the sound side, not only before a change of its lines.

## What the third round found (`--jumps`, `--rom-reads`, 27-11-2026)

- **MAME's core changed in one thing**: its RDOP sets `m_fetching` while it reads the instruction stream (the
  4-byte prefetch included), since the core reads its instructions through RDMEM, as its data; said in
  tlcs900.cpp's header. ngpref leaves those reads out, and its own (the disassembler's, the stack's).
- **`--jumps`**: the JP and CALL whose memory operand is a register's (prefixes B0-BF, F3-F5), when taken. In
  `neo_south_island.txt` (3000 frames), 134 pairs from 10 instructions: 23774B (`call T,XWA`, 100 targets),
  23E50A (7), 39DCC5, 39DCDA, 39DF41, 3F1D58 (`call T,XIX` through the BIOS's table at FFFE00: FF2D27,
  FF2D33), and in the BIOS FF1FB1, FF35F5, FF540C, FF5410. Every target was executed, and the log of frames
  1640-1800 has all of the 1278 such jumps run there in the list, with their targets.
- **An interrupt between a jump and its target**: the next instruction is then the handler's, and the target is
  the PC the interrupt pushed (6 bytes: the PC, then the SR, tmp95c061.cpp's tlcs900_check_irqs). It happens 9
  times in the scenario, all after 2000E7's `call NZ,XWA` not taken (VBLANK, FF22B7): the PC pushed is 2000E9,
  the instruction after the handler's RETI in the log, and nothing is listed.
- **`--rom-reads`**: 9729 ranges, 84256 bytes by instruction, read by 236 instructions (210 of the cartridge,
  24 of the BIOS, 2 in RAM: 006E35 and 006E5A, the game's flash routines, reading the save area 3F8000-3FABFF).
  None of those bytes was executed; two tables sit right after code: 39C705 (read by 39C6F7, after the RET at
  39C6FC) and 39DF43 (read by 39DF3C, after 39DF41's JP).
- **The check**: the state, picture and sound hashes and the trace are the same as before, with the options and
  without them, and the lists are the same run after run.

## What the fourth round found (the runtime's K2GE, 27-11-2026)

- **What a line is**: MAME's K2GE draws pens, not colours: 0-191 the colour palettes' entries, 192-215 the
  K1GE-compatible mode's (each through its register at 100-117), 216 the background, 217 the outside of the
  window; the pens of 192 on become colours through the registers (012, 100-117, 118) as they are when the
  picture is shown, at the end of the frame. The runtime's K2GE (console-decomp `ngp/runtime/src/k2ge.c`,
  `ngp/k2ge.h`) draws the same pens, a byte each, from the chip's 16 KB read in place; the window is taken at
  the start of line 0, and line N is drawn at the start of line N + 1.
- **The check, two ways**: `test_k2ge` writes 28 dumps of the chip's memory (`ngpref --dump`: the BIOS's setup,
  its logo, SEGA, the title, the menu and the zone) to MAME's K2GE and compares every line and every pixel's
  colour, each dump also with its planes swapped, in the K1GE-compatible mode, with a small window and with its
  sprites past column 255: 140 pictures, the same. And in `ngpref` the runtime's K2GE draws every line when
  MAME's does: in `neo_south_island.txt` (3000 frames) and `setup.txt` (2599) no line differs, and the state,
  picture and sound hashes are the same as before.
- **What MAME's arithmetic keeps**: a sprite's column is 8 bits (`spr_x` is a u8), so one past column 255 shows
  at the left edge; the first draft took it as an int, and only the moved sprites caught it.
- **The local worker**: it drafted k2ge.c from the header and k1ge.cpp's ranges against the check; two slips
  were fixed by hand (a missing `<stdbool.h>`, the K1GE mode's register index truncated to 8 bits), and the
  8-bit column above. Its fixes were sent to the remote server first (`remote.escalate`), which refused them
  (HTTP 400).

## What the fifth round found (the runtime's board, 27-11-2026)

- **The board** (console-decomp `ngp/machine.h`, `ngp/runtime/src/machine.c`): ngp.cpp's driver in C, as
  `md_board` is the Mega Drive's: the memory map, the I/O at 000080-0000BF (the clock, the pad, the power button
  and its NMI, the sound's ports, the Z80's lines), TO3 on port A, the NVRAM (MAME's ngpc.nv) and the flash. The
  chips are the host's, through hooks: the TMP95C061's own registers, the K2GE, the sound side. ngpref runs on
  it now; ngp.cpp's console is gone from ngpref.cpp (275 lines less).
- **The cartridge is read in place**, as an ESP32's flash would hold it: the board keeps in its RAM 32 KB from
  `GAME_SAVE_BASE` (game/data.h) and, for each chip, the 16 bytes MAME's flash_w overwrites with its IDs and puts
  back whenever the chip returns to reading. What MAME would change outside them is counted (`flash_lost`), and
  ngpref says it at the end: 0 in both scenarios.
- **The BIOS writes the cartridge too**: as it starts it programs a byte of AA in the block after the game's
  save area (3FC000-3FFFFF): 3FE000 in the BIOS's setup, 3FDF00 in the zone's scenario, the place depending on
  its NVRAM (its write sequence at FF74C6, the program at FF3018). With only the save area (16 KB) kept, the
  BIOS read FF back and took another path (56 writes to the cartridge instead of 26084): the board keeps both,
  3F8000-3FFFFF. The state's hash takes the first 16 KB, as it always did.
- **The check, two ways**: ngpref on the board gives the baseline's hashes of the state, the picture and the
  sound in every frame of `setup.txt` and `neo_south_island.txt`, the same trace and the same NVRAM; and
  `test_flash` runs the board's flash and MAME's flash_w (flash.hxx, as it is) side by side on random command
  sequences, over cartridges of 512 KB, 1, 2 and 4 MB (every block erase, program, ID read and block protect
  reached in each), and fails on five mutants of the board.
- **The local worker**: it drafted machine.c (two arrays declared const, fixed by hand) and test_flash.cpp,
  then rewrote machine.c against both checks (its power on copied the 32 KB it keeps to the stack, too much for
  an ESP32's; the ID places as one table), wrote its comments (the code the same token for token) and tidied the
  test. The test found two faults of the first draft the scenarios could not see (the program writes 5555 AA
  right after every erase, which leaves both states for reading): a block erase left the chip in PROG2, not
  AUTO_BLOCK_ERASE, and every erase cleared the ID bytes at 0-3. Both are mutants the test must fail on now,
  with three more. The rule it was given for `flash_lost` was mine and too strict (a program can only be
  weighed against the cartridge's own byte); fixed in the test.

## What the sixth round found (the runtime's T6W28, 27-11-2026)

- **The chip** (console-decomp `ngp/t6w28.h`, `ngp/runtime/src/t6w28.c`): MAME's t6w28.cpp in C, a struct the
  host keeps (about 200 bytes), integers only; the volume table is set_gain(0)'s, 16 integers MAME computes in
  doubles.
- **What MAME's arithmetic keeps**: the sound is port 1's three tones and port 0's noise; port 0's tone 2 runs
  only for the noise's "tone 2" rate, and port 0's tones 0 and 1 and port 1's noise are never run. Output 0 (the
  left side) takes port 1's volumes, output 1 (the right side) port 0's. A voice that is off has its counter
  moved on by the whole run of samples at once, so the samples depend on where the runs are cut: the runtime
  makes a run as one of MAME's stream updates (ngpsound cuts them before every write, at a DAC's write and at
  the end of a frame; set_enable does not update the stream in MAME, so it takes effect from the last cut). The
  sums of products overflow MAME's int and wrap; the C takes them as unsigned 32-bit, the same bits. A run is
  at most 16383 samples, past which a silent voice's 32-bit counter would overflow (a frame is 3203).
- **The check, two ways**: `test_t6w28` runs MAME's chip and the runtime's on random writes, enables and runs
  of samples (400 cases, 225959890 values, every noise mode and every volume on both ports, white and periodic
  noise, the longest run, a run before the first enable), the same; it fails on 11 wrong chips (the volume
  table, the silent voices' counters, the noise's mode, inversion, rate and reset, the outputs' volumes, the
  enable and the reset's, the clamp). A twelfth, port 0's tone 2 not run, gives the same samples: only its
  period is heard (the noise's "tone 2" rate), and it runs to keep the state MAME's. And in `ngpref` the
  runtime's chip runs beside MAME's in the sound side, every value compared: in `setup.txt` (2600 frames) and
  `neo_south_island.txt` (3000) none differs, and the state, picture and sound hashes, the trace and the NVRAM
  are the same as before. With one entry of the volume table off by one, the zone gives 620354 values unlike.
- **test_ngpsound** is built by CMake now (it was built by hand), and passes.
- **The local worker**: it drafted t6w28.c right at the first try (my first compile check refused it: its
  `| head` always succeeded), and rewrote it against an equivalence check (the draft and the rewrite on the
  same random operations, the same samples and state); the wording by hand. Its first test built MAME's chip
  on the stack, where the zeroed operator new never runs (port 1's registers and the noise modes are then the
  stack's leftovers), and wrote the wrong registers in its setup; sent back with the faults, it fixed them but
  took the latch bit for a register bit (`(data >> 4) & 0x0f`), so its noise coverage never held: that line, the
  run before the first enable (the reset's mutant lived without it) and the wording by hand.
- **Left for the sound**: the mix. MAME's DAC_8BIT_R2R (dac.cpp) is not in the repository; ngpsound takes a
  DAC's level as its byte / 255, an approximation, and mixes in floats. The DACs are the bytes the board passes.

## What the seventh round found (the runtime's K2GE registers and timing, 27-11-2026)

- **The registers and the lines** (console-decomp `ngp/k2ge.h`, `src/k2ge.c`): MAME's k2ge_device::write,
  k1ge_device::read, timer_callback and device_reset on the chip's 16 KB in place. A frame is 199 lines of 515
  dots; at the start of every line the chip sets (lines 152-198) or clears (line 0) the VBLANK status, bit 6 of
  010, calls VBLANK (INT4) with 1 on lines 152-198 and with 0 on line 0 when 000 bit 7 is set, calls HBLANK (TI0)
  with 1 on lines 0-150 and 198 when 000 bit 6 is set, and calls it with 0 at their dot 480 whether or not it
  raised it. A write to 000 calls VBLANK too (bit 7 ? the status : 0). MAME calls a line with its state even
  when it is at that state already; the runtime says each call, and the host passes it on as ngp.cpp does.
- **What MAME's writes keep**: 100-117 keep 3 bits, the palettes' high bytes 4, 7E2 bit 7 and only while 7F0
  is AA (else the write is lost, so the reset's write to 7E2 is); 030 is stored whole, since k1ge_device::write
  keeps its bit 7 and k2ge_device::write then stores the byte again as it came. RAS.H (008) reads dot / 4, RAS.V
  (009) the line.
- **The check in ngpref**: the runtime's registers keep their own 16 KB, which every write of the CPU reaches
  as it reaches MAME's; every read is compared, and at the end of every frame the memories and the calls of
  both lines; the runtime's lines are now drawn from its own memory. In `setup.txt` and `neo_south_island.txt`
  nothing differs, and the hashes, the trace and the NVRAM are the same as before. With HBLANK called on line 151
  too, every frame's calls differ; with RAS.H as dot / 2 nothing does: neither the BIOS nor the game reads 008
  in the scenarios, which the random test covers.
- **The random test**: `test_k2ge_registers` drives MAME's K2GE and the runtime's with the same writes, reads
  and times (200 cases, 800000 operations, 2960160 VBLANK and 27813005 HBLANK calls), comparing the memories,
  the reads and both lines' calls after every operation; every register kind, both 7E2 cases, RAS.V on every
  line and RAS.H at every value. It fails on 14 wrong parts (the masks of 030, 117, 118 and the palettes, 7E2's
  lock, the VBLANK call of a write, HBLANK on line 151, the status, RAS.H, the reset, the HBLANK off, VBLANK
  from line 151) and on one that keeps no mask and makes no call.
- **The local worker**: it wrote the registers' functions against a check of the facts above (k1ge.cpp's
  values, written down from its source), right at the third try. Its test compiled at the third; my check then
  refused it wrongly (it built its wrong part on k2ge.c with the new functions already in it). Reviewed, the
  test passed four of five wrong parts: it never wrote 117 or 118 nor any offset, read nothing above 0FF0, and
  its lists' lengths were never compared; sent back with them and a check on those parts, it fixed most at the
  first try, and the 100-118 offsets and the coverage of a line's own VBLANK calls by hand.

## The steps, each with its check

1. **Repositories**: `spa-decomp` (tools/core = arcade-decomp, tools/console = console-decomp on `ngp`) and
   `spa-port`, as TMNT. Check: the submodules at their commits, `rom/` ignored. Done 26-11-2026 for spa-decomp.
2. **`ngpref`** (console-decomp `ngp/reference/`): MAME's TMP95C061 core, MAME's Z80 and T6W28, and MAME's K2GE
   adapted to run without MAME's device framework, against the runtime's console; the real BIOS. Check: from a
   controls script it boots the BIOS, the SEGA screen, the title and a zone; BMP frames and hashes per frame (state,
   picture, sound); `--trace`, `--jumps`, `--rom-reads`. Done 26-11-2026, `--jumps` and `--rom-reads` 27-11-2026;
   the console is ngp.cpp's in `ngpref.cpp` until the runtime's (step 3).
3. **The runtime's console** (`ngp/runtime/`, the resource bar above): memory, TMP95C061 timers and interrupts,
   K2GE a line at a time, T6W28 and DACs, flash, pad; and **the BIOS in C** (boot, the RAM it leaves, the vectors, the
   5 calls). Check: `ngpref` with the runtime's K2GE gives MAME's K2GE picture; with the BIOS in C, the same hashes as
   with the real one. The K2GE done 27-11-2026; the board (memory, I/O, clock, pad, flash, NVRAM) 27-11-2026; the
   T6W28 27-11-2026; the K2GE's registers and lines' timing 27-11-2026 (beside MAME's: the chip's memory is
   still MAME's for the CPU); the TMP95C061's timers and interrupts and the mix still the host's (above).
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
