/**
 *    Name:        data.h
 *    Description: the cartridge's program and the console's BIOS as the console has them, for the tools that
 *                 run the original code
 *    Version:     0.1.0
 *    Created:     26-11-2026
 *    Modified:    26-11-2026
 *    Author:      Sebastian Toyos
 *
 *    license:BSD-3-Clause
 *    The reference (tools/console/ngp/reference) runs the original code, so it fills this from the player's
 *    dumps when it starts (game/extract.h). The game itself never opens them.
 */
#ifndef GAME_DATA_H
#define GAME_DATA_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define GAME_PROGRAM_SIZE   0x200000     /* the cartridge: 16 Mbit of flash at 200000, the TLCS-900/H's program,
                                            its data, the Z80's sound driver and the save area (3F8000-3FBFFF) */
#define GAME_BIOS_SIZE      0x10000      /* the Neo Geo Pocket Color's BIOS at FF0000 (the reference only) */

extern uint8_t game_program[GAME_PROGRAM_SIZE];
extern uint8_t game_bios[GAME_BIOS_SIZE];

#ifdef __cplusplus
}
#endif

#endif
