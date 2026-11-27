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
- **The BIOS** (27-11-2026): its boot in C in the runtime (step 3); its routines the program goes on using are
  translated and decompiled with the game (steps 5-7), from the player's BIOS dump as the game from the cartridge.
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

## What the eighth round found (the runtime's TMP95C061 devices, 27-11-2026)

- **The chip** (console-decomp `ngp/tmp95c061.h`, `ngp/runtime/src/tmp95c061.c`): MAME's tmp95c061.cpp
  without the core, a struct the host keeps: the registers at 000000-00007F, the ports, the 8-bit timers and
  their prescaler, the A/D, the input lines, the micro DMA (through the host's bus) and the choice of the
  interrupt taken. What the core does is the host's (the pushes, the IFF, the vector, HALT, the EI and RETI
  shadow); the choice is split in two (`pending`, then `acknowledge` after the pushes and the vector's read),
  so that MAME's order is kept.
- **What MAME's code keeps**: a timer's match raises its request but does not set m_check_irqs, so the
  interrupt waits for something else to (HBLANK's TIO every line, a write of an interrupt register, EI...);
  the prescaler keeps 24 bits after each run. At a priority the last source of MAME's table wins, priorities
  0 and 7 are never taken, and the NMI leaves the SR's IFF. A micro DMA channel whose start vector's request
  is set ends the scan even when its mode is none of MAME's 16 (it moves nothing, counts down and clears the
  request); modes 0C and 10 read 16 bits to write 8. MAME raises 14 of the 22 maskable requests: not the
  serial receptions, the 16-bit timers' (they are not run) nor INT6 and INT7 (no line), since a write keeps a
  request bit or clears it, never sets it. 012's write is port 7's latch (MAME's map); ports 2 and 6 have no
  read callback, port 9 no write one.
- **MAME's constructors leave m_timer_8 unset** (and m_timer_pre until the reset): ngpref's TMP95C061 is now
  static, built in zeroed memory, with the same hashes as before.
- **The check, two ways**: `test_tmp95c061` drives MAME's chip and the runtime's with the same random writes,
  reads, lines, runs (up to 300000 cycles), micro DMA and interrupt checks: 300 cases, 900000 operations
  (16507 interrupts taken, 6591 NMIs, 2201 DMA moves, 8178 A/D ends, 2591 timers' requests, TO1 and TO3
  changed 230 and 211 times), the same, the DMA's bus reads too; it fails on 30 wrong chips (the timers'
  clocks, 16-bit modes and flip-flops, the prescaler, TRUN and TFFCR, port A's mask, the edges of TIO, INT4,
  NMI, INT0's level, INT5's bit, the requests' writes, the choice's start, level and order, the
  acknowledge, the A/D's time and ADREG, DMA mode 0C). And in `ngpref` the runtime's chip runs beside MAME's
  (the same writes, lines and cycles; every read, interrupt, DMA check and step compared, the registers at
  the end of every frame): in `setup.txt` (15438 interrupts) and `neo_south_island.txt` (16024) nothing
  differs, no micro DMA moves, and the hashes, the trace and the NVRAM are the same as before; with an
  interrupt's level one less, 6991 interrupt checks differ in 600 frames.
- **The local worker**: it drafted the chip right at the first try against `facts.c` (what I read in
  tmp95c061.cpp), and the random test then found four faults the facts did not reach, a line each, fixed by
  hand: two writes out of their arrays (040-043's and 05C-05F's indices, which overwrote the pattern
  generator), modes 0C-0E counting the destination down instead of the source, and a channel with an unknown
  mode not ending the DMA's scan. Its test compiled at the third try; by hand, its runtime chip was built and
  reset once for all cases, an interrupt pushed the new SR in place of the PC, a start vector was written as
  an address, its coverage was counted out of its array, and every operation was as likely (a reset every
  ten). Two of its 30 mutants were equivalent (0xffffff for 0x00ffffff, a loop run backwards), replaced by
  hand; the test then let two through (T256: no long runs; mode 0C read as 8 bits: the bus's reads not
  compared), now caught. Its ngpref block ran at the second round, with five faults fixed by hand: MAME's
  line numbers taken as consecutive, two offsets, the DMA's replay erasing what it then compared, a text
  written for every difference (the third round ran out of time), and in that third round a fact made up
  (the reset's prescaler at 1). Claude Code stopped one of its batches when the computer ran short of memory
  (llama-server holds 25 GB).

## What the ninth round found (the runtime's mix, 27-11-2026)

- **MAME's DACs**: ngp.cpp's two DACs are DAC_8BIT_R2R (dac.cpp, now in console-decomp `ngp/reference/mame`,
  MAME 0.289's as it is). With nothing routed into them a byte gives -1 + byte / 128: 80 is the middle and 00
  the bottom, and both start at 00. ngpsound took a byte as byte / 255 (0 to 1), which put an offset on every
  value it wrote out. The speaker sums 0.50 of each T6W28 output (value / 32768) and 0.25 of its side's DAC;
  in MAME's floats that sum is exact. dac.cpp builds unchanged on arcade-decomp's sound stand-in with four
  members of MAME's sound_stream more (fill, get, input_count, and the device's requested inputs, none here).
- **The mix** (console-decomp `ngp/mix.h`, `src/mix.c`): a run of the T6W28's samples with the DACs' bytes,
  t6w28 / 2 + (byte - 128) * 64 a side with 1.0 as 32768, the half of an odd value dropped: -8192 to 24511, no
  clamp, integers only. A host cuts its runs at a DAC's write, as ngpsound already did. ngpsound now mixes with
  MAME's DACs (the WAV is MAME's sum), and the runtime's mix runs beside it, every value compared.
- **What the game does with them**: only the SEGA voice. FadeToTitle calls WAVE_OUT (at 23AFAB) with timer 2
  (T23MOD, TREG2 6), whose interrupt writes each byte to both DACs with one word write (mono), 8080 as its rest.
  So timer 2 is used too, not only 0 and 1. The disassembly calls A2 `DAC_Left`, but ngp.cpp writes 0x22 to its
  right DAC; for this game it is the same byte. Until the voice the DACs are at 00, and MAME's sum carries
  -0.25 (-8192) on both sides, then 0 from the voice on: a step of the output's level the port will hear as a
  click unless it takes the constant out (step 8 decides).
- **The check, two ways**: `test_mix` runs MAME's DACs with ngp.cpp's gains against the runtime's mix on every
  T6W28 value with every byte on both sides (256 runs of 32768 samples) and on 20000 random runs (half in place,
  a guard past each): 99266738 values, the same; it fails on 9 wrong mixes (byte / 255, no middle, the middle at
  7F, the odd half rounded up, the T6W28 at a gain of 1, the two top values held, the DACs or the sides
  crossed, the last sample left out). And in `ngpref` the runtime's mix of the runtime's T6W28 samples gives
  MAME's sum in every value of `setup.txt` and `neo_south_island.txt`, and the hashes, the trace and the NVRAM
  are the same as before (they never took the mix). With a mix one off only for the bytes other than 00 and
  80, the zone gives 591068 values unlike: 295534 samples, the voice's 1.54 seconds.
- **The local worker**: it drafted `test_mix` against a check that built it on the right mix and on the nine
  wrong ones. Its first try left out `<cstdarg>`, which the stand-in needs, and so did its first fix. The
  second fix built, but its in-place runs took MAME's sums from the buffer the mix had just written over. Sent
  back with that fault, it fixed it at the first try. By hand: the DACs built as ngpsound builds them (its
  draft zeroed their memory, which dac.cpp does not need and which would hide a member left unset), the
  constructor's arguments, and the cases counted in its last line.

## What the tenth round found (what the program takes from the BIOS, 27-11-2026)

- **The hand-over**: the BIOS starts the cartridge at its entry (the header's 20001C: 200040) in frame 455 of
  `neo_south_island.txt` and 1850 of `setup.txt`. Its last steps (FF1F66-FF1C84): the K2GE's scroll planes and
  colour palettes cleared, every RAM vector at 6FB8 set to FF23DF (a RETI) and the VBLANK's at 6FCC from its table
  at FF23C3, the watchdog cleared, then `pushw (6C02); pushw (6C00); ldf 0; ret`: the entry it keeps at 6C00, in
  bank 0. From there to SEGA (525) the screen is black: nothing of the logo is seen again.
- **`ngpref --handover FILE`** (console-decomp `ngp/reference/handover.hxx`): from power on to the hand-over, the
  BIOS's writes (which bytes, and each register's last value and count); from the hand-over to the end of the run,
  the bytes the program reads before writing them (with their values at power on and at the hand-over, and whether
  the BIOS set them or they are the NVRAM's), and the BIOS's code it enters, from where and why. The hashes, the
  trace and the NVRAM are the same with and without it.
- **What the program reads of what the BIOS left** (the zone's 3000 frames; `setup.txt` reads the same until the
  power button):
  - by the game's own code, 10 bytes: TRUN (020) 80, 025 FC and T23MOD (028) 00 as they read, `Z80Comm` (0BC) FC
    (the BIOS's last write there was 03: FC is its Z80 driver's), 6C58 03 and 6C59 00 (`WRITE_FLASH_RAM`), 6C28 00,
    and `NgpOSMode` (6F91) 10, which in the zone the BIOS does not write: it comes from the NVRAM, written at the
    first setup;
  - by the BIOS's routines the program goes on running: about 25 of its variables (6C16-6C26, 6C5F, 6D05, 6DA2,
    6E80, 6F80-6F8A), the I/O 0B2 and 0B3, its table at FFFE00 (entries 1, 2, 15h, 16h), the vectors at FFFF00
    (SWI 1, INT4, INT5, INTT2, INTAD) and the return address its SWI dispatcher pushes (FF279E-FF27A1);
  - the console's, not the BIOS's: the clock (091-097, by VECT_RTCGET in frame 1407), the pad (0B0), the power
    button (0B1), the A/D's result (060-061);
  - none of the K2GE's 16 KB and none of the Z80's RAM, where the BIOS changed 3406 and 3470 bytes (the logo, its
    sound driver), and none of the save area;
  - 6 bytes at 6E62-6E75 "fetched", none executed: the core's prefetch past the last instructions of the game's
    flash routines, which it copies to 6E00.
  - One of them depends on how long the BIOS ran: 6C18-6C19, the frames since its last A/D (01BF in the zone, 000A
    in the setup), which says when the next battery reading comes (frame 612 in the zone).
- **The BIOS's code after the hand-over**: 177 instructions in the zone. The handlers of FFFF00's vectors: INT4
  (VBLANK, FF2163: the pad, the power button, the A/D's count, the automatic power off, then the game's vector at
  6FCC), INT5 (FF2282, the Z80's, to 6FD0), INTT2 (FF22B7, to 6FDC: the SEGA voice's timer 2, 12984 times; 35
  times inside the VBLANK's handler, whose RETI returns there) and INTAD (FF2DCE). SWI 1 (FF2772) with VECT_CLOCKGEARSET
  (W3=01) and VECT_RTCGET (FF1440); in the setup also VECT_SHUTDOWN (W3=00), then the BIOS's power off, which reads
  4096 bytes of its own ROM (FF34B6). And the two calls of SYSTEM.LIB's `SYSTEM_CALL` through FFFE00 (FF2D27,
  FF2D33), 2541 times each.
- **The console as the BIOS sets it** (498 register writes before the hand-over): the memory controller (038-048),
  the ports and the serial (051-05F), the timers (020-028), the A/D, the watchdog (WDCR 06F written 461 times) and
  the interrupt levels (068-07B), the board's I/O (080, 0B2-0BC: AA at 0B8 and 0B9, the sound chip and the Z80
  enabled), and the K2GE (8000 = C0, the window, the scrolls, the colour mode 87E2 = 00 behind its lock at 87F0,
  the palettes cleared).
- **The state hash never had the SR**: it asked MAME's core for TLCS900_SR, which is not one of its state entries
  (tlcs900.cpp adds the SR as STATE_GENFLAGS), and got 0. Now it reads STATE_GENFLAGS: every frame's state hash
  changes, the pictures, the sound, the trace and the NVRAM are the same as before, and the hashes are the same
  run after run (`build/runs/handover/`).
- **Decided** (proposed by Claude, confirmed by Sebas on 27-11-2026): the BIOS's routines the program reaches are
  code the scenarios run, and like the game's they must keep its flags and its stack byte for byte. So they go
  through steps 5 to 7 with the game (the translator reads them from the player's BIOS dump as it reads the game from the cartridge, and their C
  is the decompiled C) instead of being written by hand in step 3. The BIOS in C of step 3 is its boot,
  `ngp_bios_boot`: the writes that leave the console as the BIOS leaves it for the program (the lists above, named),
  through the board's bus or a host's callback, with what depends on the moment (the A/D's count) and on the
  settings (the language, the clock) given by the host.
- **The local worker** drafted `handover.hxx` against a check that builds ngpref, runs 700 frames twice and tests
  the file against what was known (the hand-over in 455, SWI 1 with W3=01, FFFE04 read, about 245 VBLANKs, the
  registers the BIOS set). Its first draft compiled at the third try and missed the BIOS (its range ended at
  100000), folded the 24-bit addresses on 3FFFFF, never looked at what had been written, and read the SR as
  TLCS900_SR. Sent back with those, its first answer was right; two of its "failures" were the check's (a path
  without `.exe`, the BIOS read at F279E). By hand: the I/O C0-FF read past its 64-byte copy, the save area's
  values, the bitmaps' size, the addresses masked to 24 bits, and the BIOS's writes (set or kept, the registers).
  Its review of the diff went through every line calling it a defect and then clearing it, until it was cut; asked
  to think first and give only conclusions, it found one: with no hand-over the file compared the power-on copies
  with zeros (now it says `handover none` and stops there).

## What the eleventh round found (the BIOS's boot in C, 27-11-2026)

- **`ngp_bios_boot`** (console-decomp `ngp/bios.h`, `src/bios.c`): the writes that leave the console as the BIOS
  leaves it for the cartridge, through the host's write (the board's `ngp_write8` in a game), and the CPU's
  registers. The TMP95C061's registers (58 on the first boot, 38 at the restart), the I/O (B2-BC, and 090-09B on
  the first boot), the K2GE (450 or 456 writes: the window, the scrolls, the mono palettes at 8100-8118, the colour
  palettes at 8200-837F cleared but their colour 0, 8380-83FF's grey ramp eight times, the LED, the colour mode
  behind its lock at 87F0), 32 of the BIOS's variables in the work RAM, the cartridge's entry it keeps at 6C00 and
  the 18 RAM vectors at 6FB8, all FF23DF (a RETI). The host gives the frames since the last battery reading (6C18),
  the language (6F87) and, on the first boot, the date's bytes at 091-097.
- **Two paths, as MAME starts the BIOS**: from its reset vector when the NVRAM was not loaded, and at FF1800 when it
  was (ngp.cpp's machine_reset). The first sets 40 registers the restart does not: the ports (001-01F, 02C-02F), the
  clock (090-09B), the T6W28's A0 and A1, and the K2GE's 810D-810F and 8115-8117; at the restart they are as the
  reset or the NVRAM left them. Every register both paths write has the same last value in both.
- **What it leaves out**: the BIOS's writes to the sound side's ports (A0 and A1, FF on the first boot, and BA, the
  Z80's NMI), whose effect is the sound chips' state, not a byte the program reads; and the bytes the BIOS changed
  that the program never reads before writing them (1553 of the RAM and 3279 of the K2GE in the zone, 1832 and 4271
  in the setup: its logo, its stack, its own variables). **B8 and B9 at AA are the sound chip off and the Z80
  stopped** (ngp.cpp: 55 on, AA off; hardware.md said "on", now fixed); 0BC is FC, the byte the BIOS's Z80 driver
  answered after the BIOS's last write there (03).
- **`ngpref --boot FILE`** (boot.hxx): at the hand-over, the boot in C runs with what the host gives taken from the
  BIOS's run, and its writes are put in place of what the BIOS left: the work RAM and the I/O from their power-on
  copies, the K2GE's 16 KB from its reset (`ngp_k2ge_reset`; its status at 010, the chip's timing, kept; MAME's
  memory replaced with `nv_load`, no write's side effects). The CPU's registers and the TMP95C061's own registers
  (its chip keeps running) are compared instead, with the hand-over's and with the BIOS's last writes; the time, the
  Z80 and the sound chips are kept. The file has an `unlike` line for each difference, and at the end of the run one
  for each byte the program read before writing that the BIOS had set and the boot did not write.
  **`--bus-hashes FILE`**: a hash a frame of every byte the TMP95C061 fetches, reads or writes, with its address.
- **The check**: `unlike 0` in both scenarios, and the pictures, the sound, the program's bus and the trace the same
  as without `--boot` in every frame of both. The state hashes differ from the hand-over on (frames 455-3000 of the
  zone), and so does the setup's NVRAM, for the bytes left out. Without `--boot` the hashes of the state, the picture
  and the sound, the trace and the NVRAM are the same as round `handover`'s (`build/runs/r11/`). Four mutants fail:
  6F83 left out (`unlike read`, and the bus from the hand-over, the sound and the picture later), the battery's
  count one more (`unlike ram`, the bus), the background colour 81 (`unlike k2ge`; the picture is the same) and XIZ
  one more (`unlike cpu`; the bus is the same): the comparison catches what the run does not show.
- **What this check does not reach**: the sound chips' state at the hand-over (the T6W28's registers after the
  BIOS's writes and its Z80 driver's, the Z80 stopped with that driver in its RAM) is kept, so a port must leave it
  as the BIOS does, or show it does not matter: step 7 checks it, the sound the same from power on. The CPU's
  registers are compared, not put in place: being the same, it is the same run.
- **The local worker** drafted `bios.c` from the lists of `--handover`, a table of the RAM's variables (what the
  BIOS's code does with each, which it had mapped from the 890 instructions the BIOS runs after the hand-over, and
  Claude checked in that code) and the names' sources, against a check that builds ngpref and runs both scenarios
  with `--boot` (it fails on the boot that writes nothing). Right at its second try. Its names were invented or
  copied (TFFCFR, COMMState on B3-B5, "REF" on 87F4, "LED Frame" on 87F2, 87F0's lock the other way round, T4MOD
  and T5MOD as the 8-bit timers and the serial channel, BEXCS as the A/D) and the RAM had no comments: sent back with
  the list, with the same check: right at its third try, every write the same; the lock's wording and a few long
  lines were fixed by hand.
  Its review of `boot.hxx` found nothing. The server elsewhere refused both requests the spill sent it (HTTP 400,
  invalid_request); the local worker answered them.

## The steps, each with its check

1. **Repositories**: `spa-decomp` (tools/core = arcade-decomp, tools/console = console-decomp on `ngp`) and
   `spa-port`, as TMNT. Check: the submodules at their commits, `rom/` ignored. Done 26-11-2026 for spa-decomp.
2. **`ngpref`** (console-decomp `ngp/reference/`): MAME's TMP95C061 core, MAME's Z80 and T6W28, and MAME's K2GE
   adapted to run without MAME's device framework, against the runtime's console; the real BIOS. Check: from a
   controls script it boots the BIOS, the SEGA screen, the title and a zone; BMP frames and hashes per frame (state,
   picture, sound); `--trace`, `--jumps`, `--rom-reads`. Done 26-11-2026, `--jumps` and `--rom-reads` 27-11-2026;
   the console is ngp.cpp's in `ngpref.cpp` until the runtime's (step 3).
3. **The runtime's console** (`ngp/runtime/`, the resource bar above): memory, TMP95C061 timers and interrupts,
   K2GE a line at a time, T6W28 and DACs, flash, pad; and **the BIOS's boot in C** (the state it leaves for the
   program, which `ngpref --handover` lists; its routines the program reaches go with the game, steps 5-7, as
   decided in the tenth round). Check: `ngpref` with the runtime's K2GE gives MAME's K2GE picture; with the
   boot in C put in place of the BIOS's at the hand-over (the RAM from power on, the K2GE's memory from its reset,
   the CPU's registers; the time, the Z80 and the chips' counters kept), the same pictures, sound and program's bus
   in every frame of both scenarios, and the registers it writes the BIOS's. The K2GE done 27-11-2026; the board
   (memory, I/O, clock, pad, flash, NVRAM) 27-11-2026; the T6W28 27-11-2026; the K2GE's registers and lines' timing
   27-11-2026 (beside MAME's: the chip's memory is still MAME's for the CPU); the TMP95C061's devices (timers,
   interrupts, micro DMA, A/D) 27-11-2026 (beside MAME's: the core is MAME's); the DACs and the mix 27-11-2026;
   what the program takes from the BIOS (`--handover`) 27-11-2026; the BIOS's boot in C (`--boot`) 27-11-2026.
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
