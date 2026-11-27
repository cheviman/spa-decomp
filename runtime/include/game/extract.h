/**
 *    Name:        extract.h
 *    Description: the player's dumps into the console's memory (game/data.h), for the tools that run the
 *                 original code
 *    Version:     0.1.0
 *    Created:     26-11-2026
 *    Modified:    26-11-2026
 *    Author:      Sebastian Toyos
 *
 *    license:BSD-3-Clause
 */
#ifndef GAME_EXTRACT_H
#define GAME_EXTRACT_H

#ifdef __cplusplus
extern "C" {
#endif

/* Reads the cartridge from 'source' (a .zip, a ROM file, or a folder holding either) into game_program,
   checked by its CRC32 and size. NULL when it is there; otherwise what is wrong, for a message */
const char *game_rom_set_load(const char *source);

/* The same for the console's BIOS into game_bios: only the reference runs it */
const char *game_bios_load(const char *source);

#ifdef __cplusplus
}
#endif

#endif
