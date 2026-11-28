"""
Name:        object_scenarios.py
Description: the objects of every level of the cartridge, and controls scripts that bring the player to one object
             of each kind in each act
Version:     0.1.0
Created:     27-11-2026
Modified:    27-11-2026
Author:      Sebastian Toyos

license:BSD-3-Clause
The objects are the level layouts of the cartridge, read from its LvlObjList (the label's address in AS's listing
of the disassembly, build/asm/Main.lst): a table of 4-byte pointers, one per level, each pointing to the number of
X and Y screens and a table of 16-bit offsets to the screens' lists of 10-byte entries (the game's LoadObjects).
list prints every object of every level, in order; write writes one controls script per act, objects_1-1.txt to
objects_6-2.txt, for the levels 0 to 11: from a console set up and off (--nvram build/setup.nv), the debug menu by
the poke at 499C, BEGINNING, the act picked in the level select; then for one object of each ID (the star posts'
and the signpost's left out), in order of x, the lives poked to 5, the star post's variables (67D4-67DB) as if a
star post past the act's own had been touched (67DB 10) 80 pixels before the object, and the player's Y under 64
for 4 frames, the level's pit: a life lost, the player starts again there and runs right, left, right and left
around the object, 100 frames each with three jumps. An object's ID is the number its entry holds less one,
its index in ObjectPtrList, as Valley Bell's Objects.txt numbers them; the disassembly's labels number from one
(ID 0D, a star post, is obj0E_LampPost; 0E obj0F_Signpost; 0F obj10_Capsule; 10 obj11_SSRing; 11 obj12_Boss).
  py tools/object_scenarios.py list [--rom FILE] [--listing FILE]
  py tools/object_scenarios.py write [--rom FILE] [--listing FILE] [--out DIR]
"""
import argparse
import re
import sys
import textwrap
from pathlib import Path

LINE = re.compile(r"^\(\d+\)\s*\d+/\s*([0-9A-F]+) : (.*)$")
LABEL = re.compile(r"^(?:[0-9A-F]{2} )+\s*([A-Za-z_][A-Za-z0-9_]*):")
LEVEL_NAMES = ["1-1", "1-2", "2-1", "2-2", "3-1", "3-2", "4-1", "4-2", "5-1", "5-2", "6-1", "6-2"]
# Each act's zone and act, for the scripts' comments: zone 5 is Sky Chase's one act and Aerobase's
ZONE_NAMES = ["Neo South Island act 1", "Neo South Island act 2", "Secret Plant act 1", "Secret Plant act 2",
	"Cosmic Casino act 1", "Cosmic Casino act 2", "Aquatic Relics act 1", "Aquatic Relics act 2", "Sky Chase",
	"Aerobase", "Gigantic Angel act 1", "Gigantic Angel act 2"]
SKIP_IDS = {0x0D, 0x0E}    # the star posts and the signpost


def read_rom(path):
	"""The bytes of the cartridge, mapped at 200000."""
	data = path.read_bytes()
	if len(data) != 0x200000:
		print(f"{path} is {len(data)} bytes, expected 0x200000")
		sys.exit(1)
	return data


def find_label_address(listing_path, label):
	"""The address of the label in the listing, or a failure."""
	text = listing_path.read_text(encoding="latin-1")
	for line in text.splitlines():
		match = LINE.match(line)
		if not match:
			continue
		label_match = LABEL.match(match.group(2))
		if label_match and label_match.group(1) == label:
			return int(match.group(1), 16)
	print(f"{label} not found in {listing_path}")
	sys.exit(1)


def read_level_objects(rom, listing_path):
	"""The objects of every level: a list of (level, slot, id, param, x, y, extra) tuples, in list order."""
	base = 0x200000
	lvl_obj_list = find_label_address(listing_path, "LvlObjList")
	if lvl_obj_list < base or lvl_obj_list >= base + len(rom):
		print(f"LvlObjList at {lvl_obj_list:06X} is outside the cartridge")
		sys.exit(1)
	objects = []
	for level in range(13):
		pointer = int.from_bytes(rom[lvl_obj_list - base + 4 * level: lvl_obj_list - base + 4 * level + 4], "little")
		if pointer == 0:
			continue
		nx = rom[pointer - base]
		ny = rom[pointer - base + 1]
		offsets = []
		for i in range(nx * ny):
			offsets.append(int.from_bytes(rom[pointer - base + 2 + 2 * i: pointer - base + 2 + 2 * i + 2], "little"))
		for i in range(nx * ny):
			offset = offsets[i]
			if offset == 0:
				continue
			list_address = pointer + 2 + offset
			slot = rom[list_address - base]
			count = rom[list_address - base + 1]
			for j in range(count):
				entry = list_address + 2 + 10 * j
				id_plus_one = rom[entry - base]
				param = rom[entry - base + 1]
				x = int.from_bytes(rom[entry - base + 2: entry - base + 4], "little")
				y = int.from_bytes(rom[entry - base + 4: entry - base + 6], "little")
				extra = rom[entry - base + 6: entry - base + 10]
				objects.append((level, slot + j, id_plus_one - 1, param, x, y, extra))
	return objects


def list_objects(rom, listing_path):
	"""Print one line per object, every level in order and within it every screen in table order."""
	for level, slot, obj_id, param, x, y, extra in read_level_objects(rom, listing_path):
		print(f"{level:02X} {slot:02X} {obj_id:02X} {param:02X} {x:05d} {y:05d} {extra.hex().upper()}")


def build_points(objects, level):
	"""The points of the act: one per distinct ID, the instance with the smallest x among those with x >= 200,
	leaving out the star posts and the signpost; in order of x, so that the act's end, past the signpost, comes
	last."""
	points = []
	seen = []
	for obj in objects:
		if obj[0] != level or obj[2] in SKIP_IDS:
			continue
		if obj[2] in seen:
			continue
		instances = [o for o in objects if o[0] == level and o[2] == obj[2] and o[4] >= 200]
		if not instances:
			continue
		best = min(instances, key=lambda o: o[4])
		seen.append(obj[2])
		px = max(16, best[4] - 80)
		py = best[5] + 13
		points.append((obj[2], best[4], best[5], px, py))
	return sorted(points, key=lambda point: point[1])


def write_scripts(rom, listing_path, out_dir):
	"""Write one controls script per act, objects_1-1.txt to objects_6-2.txt, for the levels 0 to 11."""
	objects = read_level_objects(rom, listing_path)
	out_dir.mkdir(parents=True, exist_ok=True)
	for k, name in enumerate(LEVEL_NAMES):
		points = list(build_points(objects, k))
		a = 720 if k == 0 else 700 + 30 * (k - 1) + 50
		points_text = ", ".join(f"{obj_id:02X} at {x},{y} ({a + 300 + 800 * i})"
			for i, (obj_id, x, y, _, _) in enumerate(points))
		header = (f"{ZONE_NAMES[k]} (level {k:02X}), from a console set up and off (--nvram build/setup.nv): the debug "
			f"menu by the poke at 499C, BEGINNING, act {name} picked in the level select (A at {a}); for each point the "
			f"lives poked to 5, the star post's variables (67D4-67DB) as if a star post past the act's own had been "
			f"touched (67DB 10) 80 pixels before the object, and the player's Y under 64 for 4 frames, the level's pit: "
			f"a life lost, the player starts again there and runs right, left, right and left around the object, 100 "
			f"frames each with three jumps. The points, the object's ID at its place (the frame): {points_text}")
		header_parts = ["# " + line for line in textwrap.wrap(header, 116)]

		lines = []
		lines.append("600 poke 499C DB")
		lines.append("650 press a")
		for i in range(k):
			lines.append(f"{700 + 30 * i} press down")
		lines.append(f"{a} press a")
		for i, (obj_id, x, y, px, py) in enumerate(points):
			p = a + 300 + 800 * i
			lines.append(f"{p} poke 67AF 05")
			lines.append(f"{p} poke 67D4 {px & 0xFF:02X}")
			lines.append(f"{p} poke 67D5 {px >> 8:02X}")
			lines.append(f"{p} poke 67D6 {py & 0xFF:02X}")
			lines.append(f"{p} poke 67D7 {py >> 8:02X}")
			lines.append(f"{p} poke 67DB 10")
			lines.append(f"{p} poke 67DA 00")
			for f in range(4):
				lines.append(f"{p + f} poke 671E 20")
				lines.append(f"{p + f} poke 671F 00")
			for side in range(4):
				start = p + 380 + 100 * side
				direction = ("right", "left")[side & 1]
				lines.append(f"{start} hold {direction}")
				for j in range(3):
					lines.append(f"{start + 10 + 40 * j} press a")
				lines.append(f"{start + 95} release {direction}")
		lines.append(f"{a + 300 + 800 * len(points) + 100} end")

		path = out_dir / f"objects_{name}.txt"
		path.write_text("\n".join(header_parts + lines) + "\n")


def main():
	parser = argparse.ArgumentParser(description="The objects of every level, and the controls scripts that run past each one")
	subparsers = parser.add_subparsers(dest="command", required=True)
	for name in ("list", "write"):
		sub = subparsers.add_parser(name)
		sub.add_argument("--rom", type=Path, default=Path("rom/sonic.ngc"))
		sub.add_argument("--listing", type=Path, default=Path("build/asm/Main.lst"))
		if name == "write":
			sub.add_argument("--out", type=Path, default=Path("tests/controls"))
	args = parser.parse_args()
	rom = read_rom(args.rom)
	if args.command == "list":
		list_objects(rom, args.listing)
	else:
		write_scripts(rom, args.listing, args.out)


if __name__ == "__main__":
	main()
