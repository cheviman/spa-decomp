/**
 *    Name:        rom_set.c
 *    Description: Sonic the Hedgehog Pocket Adventure's cartridge and the Neo Geo Pocket Color's BIOS into the
 *                 console's memory (game/data.h)
 *    Version:     0.1.0
 *    Created:     26-11-2026
 *    Modified:    26-11-2026
 *    Author:      Sebastian Toyos
 *
 *    license:BSD-3-Clause
 *    The World cartridge (game 0059 in its header), known by its CRC32 and size through the console's reader. MAME's dump
 *    (356F0849) holds a default save in the flash's save area (3F8000-3FBFFF); the same dump with that area
 *    erased (8BD22145) is the same program, and both are taken. Only the tools that run the original code read
 *    them.
 */
#include "game/extract.h"

#include "game/data.h"
#include "md/cartridge.h"

#define CARTRIDGE_CRC        0x356F0849u    /* Sonic the Hedgehog Pocket Adventure (World), MAME's 'sonic' */
#define CARTRIDGE_ERASED_CRC 0x8BD22145u    /* the same, with the save area erased (FF) */
#define BIOS_CRC             0x6EEB6F40u    /* MAME's ngpcbios.rom */

uint8_t game_program[GAME_PROGRAM_SIZE];
uint8_t game_bios[GAME_BIOS_SIZE];

const char *game_rom_set_load(const char *source)
{
	if (md_cartridge_load(source, CARTRIDGE_CRC, GAME_PROGRAM_SIZE, game_program)
		|| md_cartridge_load(source, CARTRIDGE_ERASED_CRC, GAME_PROGRAM_SIZE, game_program))
		return 0;
	return "the cartridge (Sonic the Hedgehog Pocket Adventure, World: 2 MiB, CRC32 356F0849 or 8BD22145) is not there";
}

const char *game_bios_load(const char *source)
{
	if (md_cartridge_load(source, BIOS_CRC, GAME_BIOS_SIZE, game_bios))
		return 0;
	return "the Neo Geo Pocket Color's BIOS (64 KiB, CRC32 6EEB6F40) is not there";
}
