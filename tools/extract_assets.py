"""
Name:        extract_assets.py
Description: the cartridge's binary files (the ones Valley Bell's disassembly includes whole) cut from the
             player's own cartridge dump, as they are and in forms one can edit, and the check that the edited
             forms build the cartridge's bytes back exactly
Version:     0.1.0
Created:     28-11-2026
Modified:    28-11-2026
Author:      Sebastian Toyos

license:BSD-3-Clause
The cartridge's binary files are the ones Valley Bell's disassembly includes whole (binclude), listed in
assets.txt (tools/listing_map.py writes it: ADDRESS LENGTH PATH LABEL, the address at 200000 in the
cartridge, so its byte at ADDRESS is the dump's offset ADDRESS - 0x200000). The dump is the file in rom/
whose CRC32 is 356F0849 or 8BD22145 and whose size is 2097152 (the World release, with its default save or
with the save area erased). Without --check, each file is written raw, and tile sets (.til) as a PNG (16
tiles a row, 4-bit indexed, the K2GE's order: row r is the little-endian 16-bit word at tile offset 2*r,
pixel x (0 the left) is (word >> (14 - 2*x)) & 3) and maps (.map) as text (width, height, offset, then the
entries row by row); tiles.txt holds each tile set's count so the padding tiles are not part of the set.
With --check, nothing is written: each file is built back from what the output holds and compared with the
dump's bytes at its address; a tile set from its PNG (read with read_png_indexed) and its count in
tiles.txt, a map from its text, the rest from its raw copy. A file missing, a picture of the wrong size or
an index above 3, a line of the map's text not of its width, and any byte that differs are each a failure,
printed as PATH: what, at most 20 of them, then the count. It exits 1 if there is any failure, else 0.
  py tools/extract_assets.py [--rom FILE] [--assets assets.txt] [--out assets] [--check]
"""
import argparse
import os
import struct
import sys
import zlib

# Find the repository root (the folder that holds tools/core/) by walking up from this file's folder.
_d = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(_d, "tools", "core")):
	_d = os.path.dirname(_d)
sys.path.insert(0, os.path.join(_d, "tools", "core"))
from asset_formats import write_png_indexed, read_png_indexed

TILE_PALETTE = [(255, 255, 255), (170, 170, 170), (85, 85, 85), (0, 0, 0)]
ROM_SIZE = 2097152
ROM_CRC = (0x356F0849, 0x8BD22145)
CARTRIDGE_BASE = 0x200000


def find_rom(rom_dir):
	"""The file in rom_dir whose CRC32 is 356F0849 or 8BD22145 and whose size is 2097152, or None."""
	for name in sorted(os.listdir(rom_dir)):
		path = os.path.join(rom_dir, name)
		if not os.path.isfile(path):
			continue
		if os.path.getsize(path) != ROM_SIZE:
			continue
		with open(path, "rb") as f:
			if zlib.crc32(f.read()) & 0xFFFFFFFF in ROM_CRC:
				return path
	return None


def read_assets(path):
	"""The lines of assets.txt: (address, length, path, label), skipping blanks and #."""
	lines = []
	with open(path, encoding="latin-1") as f:
		for line in f:
			line = line.strip()
			if not line or line.startswith("#"):
				continue
			parts = line.split()
			if len(parts) < 4:
				continue
			address = int(parts[0], 16)
			length = int(parts[1])
			lines.append((address, length, parts[2], parts[3]))
	return lines


def tile_to_pixels(data, offset):
	"""The 8 rows of 8 pixels of the tile at offset in data (little-endian 16-bit words, K2GE's order)."""
	rows = []
	for r in range(8):
		word = struct.unpack_from("<H", data, offset + 2 * r)[0]
		rows.append([(word >> (14 - 2 * x)) & 3 for x in range(8)])
	return rows


def build_tile_png(data):
	"""The rows and count of a tile set's PNG, or None if data is not a valid tile set."""
	if len(data) < 2:
		return None
	n = struct.unpack_from("<H", data, 0)[0]
	if n < 1 or len(data) != 2 + 16 * n:
		return None
	rows = []
	tiles_per_row = min(n, 16)
	for tr in range(0, n, 16):
		pixel_rows = []
		for r in range(8):
			row_pixels = []
			for t in range(tiles_per_row):
				tile_idx = tr + t
				if tile_idx < n:
					row_pixels.extend(tile_to_pixels(data, 2 + 16 * tile_idx)[r])
				else:
					row_pixels.extend([0] * 8)
			pixel_rows.append(row_pixels)
		rows.extend(pixel_rows)
	return rows, n


def build_tile_data(rows, count):
	"""The bytes of a tile set from its PNG rows and count, or None if the picture is wrong."""
	if not rows:
		return None
	width = len(rows[0])
	if any(len(r) != width for r in rows):
		return None
	tiles_per_row = width // 8
	if width % 8 != 0:
		return None
	needed_rows = (count + tiles_per_row - 1) // tiles_per_row
	if len(rows) < needed_rows * 8:
		return None
	data = bytearray()
	data += struct.pack("<H", count)
	for i in range(count):
		tile_row = i // tiles_per_row
		tile_col = i % tiles_per_row
		base_pixel_row = tile_row * 8
		base_pixel_col = tile_col * 8
		for y in range(8):
			word = 0
			for x in range(8):
				px = rows[base_pixel_row + y][base_pixel_col + x]
				if px > 3:
					return None
				word |= px << (14 - 2 * x)
			data += struct.pack("<H", word)
	return bytes(data)


def build_map_text(data):
	"""The lines of a map's text, or None if data is not a valid map."""
	if len(data) < 4:
		return None
	w = data[0]
	h = data[1]
	offset = struct.unpack_from("<H", data, 2)[0]
	if len(data) != 4 + 2 * w * h:
		return None
	lines = [f"width {w} height {h} offset {offset:04X}"]
	for r in range(h):
		entries = []
		for c in range(w):
			entries.append("%04X" % struct.unpack_from("<H", data, 4 + 2 * (r * w + c))[0])
		lines.append(" ".join(entries))
	return lines


def build_map_data(lines):
	"""The bytes of a map from its text lines, or None if the text is wrong."""
	if not lines:
		return None
	parts = lines[0].split()
	if len(parts) != 6 or parts[0] != "width" or parts[2] != "height" or parts[4] != "offset":
		return None
	try:
		w = int(parts[1])
		h = int(parts[3])
		offset = int(parts[5], 16)
	except ValueError:
		return None
	if len(lines) != 1 + h:
		return None
	data = bytearray()
	data.append(w)
	data.append(h)
	data += struct.pack("<H", offset)
	for r in range(h):
		tokens = lines[1 + r].split()
		if len(tokens) != w:
			return None
		for token in tokens:
			try:
				data += struct.pack("<H", int(token, 16))
			except ValueError:
				return None
	return bytes(data)


def main():
	parser = argparse.ArgumentParser(description="The cartridge's binary files cut from the dump, and the check that the edited forms build the bytes back.")
	parser.add_argument("--rom", help="the cartridge dump")
	parser.add_argument("--assets", default=None, help="the assets list (default: the repository's assets.txt)")
	parser.add_argument("--out", default=None, help="the output folder (default: the repository's assets/)")
	parser.add_argument("--check", action="store_true", help="build back from the output and compare with the dump")
	args = parser.parse_args()

	root = _d
	rom_dir = os.path.join(root, "rom")
	if args.rom:
		rom_path = args.rom
	else:
		rom_path = find_rom(rom_dir)
		if not rom_path:
			print(f"no cartridge dump in {rom_dir} with CRC32 356F0849 or 8BD22145 and size {ROM_SIZE}", file=sys.stderr)
			sys.exit(1)
	assets_path = args.assets or os.path.join(root, "assets.txt")
	out_dir = args.out or os.path.join(root, "assets")

	with open(rom_path, "rb") as f:
		rom = f.read()
	entries = read_assets(assets_path)

	if args.check:
		tiles_txt_path = os.path.join(out_dir, "tiles.txt")
		tile_counts = {}
		if os.path.exists(tiles_txt_path):
			with open(tiles_txt_path, encoding="latin-1") as f:
				for line in f:
					line = line.strip()
					if not line:
						continue
					parts = line.split()
					if len(parts) == 2:
						tile_counts[parts[0]] = int(parts[1])

		failures = []
		counts = {"tiles": 0, "maps": 0, "raw": 0}
		for address, length, path, label in entries:
			offset = address - CARTRIDGE_BASE
			expected = rom[offset:offset + length]
			if len(expected) != length:
				failures.append(f"{path}: dump shorter than {length} bytes at {address:06X}")
				continue
			if path.endswith(".til"):
				counts["tiles"] += 1
				png_path = os.path.join(out_dir, "tiles", path + ".png")
				count = tile_counts.get(path)
				if count is None:
					failures.append(f"{path}: no count in tiles.txt")
					continue
				if not os.path.exists(png_path):
					failures.append(f"{path}: missing {png_path}")
					continue
				try:
					rows, palette = read_png_indexed(png_path)
				except Exception as e:
					failures.append(f"{path}: {e}")
					continue
				rebuilt = build_tile_data(rows, count)
				if rebuilt is None:
					failures.append(f"{path}: picture of the wrong size or an index above 3")
					continue
				if rebuilt != expected:
					for i in range(min(len(rebuilt), len(expected))):
						if rebuilt[i] != expected[i]:
							failures.append(f"{path}: byte {i} differs")
							break
					else:
						failures.append(f"{path}: length differs")
			elif path.endswith(".map"):
				counts["maps"] += 1
				txt_path = os.path.join(out_dir, "maps", path + ".txt")
				if not os.path.exists(txt_path):
					failures.append(f"{path}: missing {txt_path}")
					continue
				with open(txt_path, encoding="latin-1") as f:
					lines = [line.rstrip("\r\n") for line in f]
				rebuilt = build_map_data(lines)
				if rebuilt is None:
					failures.append(f"{path}: a line of the map's text not of its width or the header is wrong")
					continue
				if rebuilt != expected:
					for i in range(min(len(rebuilt), len(expected))):
						if rebuilt[i] != expected[i]:
							failures.append(f"{path}: byte {i} differs")
							break
					else:
						failures.append(f"{path}: length differs")
			else:
				counts["raw"] += 1
				raw_path = os.path.join(out_dir, "raw", path)
				if not os.path.exists(raw_path):
					failures.append(f"{path}: missing {raw_path}")
					continue
				with open(raw_path, "rb") as f:
					rebuilt = f.read()
				if rebuilt != expected:
					for i in range(min(len(rebuilt), len(expected))):
						if rebuilt[i] != expected[i]:
							failures.append(f"{path}: byte {i} differs")
							break
					else:
						failures.append(f"{path}: length differs")

		for failure in failures[:20]:
			print(failure)
		print(f"checked: {counts['tiles']} tile sets, {counts['maps']} maps, {counts['raw']} raw; {len(failures)} failures")
		sys.exit(1 if failures else 0)

	tile_pngs = []
	map_texts = []
	raw_only = []
	total_bytes = 0
	for address, length, path, label in entries:
		offset = address - CARTRIDGE_BASE
		data = rom[offset:offset + length]
		total_bytes += len(data)
		raw_path = os.path.join(out_dir, "raw", path)
		os.makedirs(os.path.dirname(raw_path), exist_ok=True)
		with open(raw_path, "wb") as f:
			f.write(data)

		if path.endswith(".til"):
			result = build_tile_png(data)
			if result:
				rows, n = result
				png_path = os.path.join(out_dir, "tiles", path + ".png")
				os.makedirs(os.path.dirname(png_path), exist_ok=True)
				write_png_indexed(png_path, rows, TILE_PALETTE, 4)
				tile_pngs.append((path, n))
			else:
				raw_only.append(path)
		elif path.endswith(".map"):
			lines = build_map_text(data)
			if lines:
				txt_path = os.path.join(out_dir, "maps", path + ".txt")
				os.makedirs(os.path.dirname(txt_path), exist_ok=True)
				with open(txt_path, "w", encoding="latin-1", newline="\n") as f:
					f.write("\n".join(lines) + "\n")
				map_texts.append(path)
			else:
				raw_only.append(path)
		else:
			raw_only.append(path)

	tiles_txt_path = os.path.join(out_dir, "tiles.txt")
	os.makedirs(out_dir, exist_ok=True)
	with open(tiles_txt_path, "w", encoding="latin-1", newline="\n") as f:
		for path, n in tile_pngs:
			f.write(f"{path} {n}\n")

	print(f"tile sets as PNG: {len(tile_pngs)} ({sum(n for _, n in tile_pngs)} tiles)")
	print(f"maps as text: {len(map_texts)}")
	kinds = {}
	for path in raw_only:
		kind = os.path.splitext(path)[1] or "(none)"
		kinds[kind] = kinds.get(kind, 0) + 1
	print(f"raw only: {len(raw_only)} (" + ", ".join(f"{count} {kind}" for kind, count in sorted(kinds.items())) + ")")
	print(f"bytes in all: {total_bytes}")


if __name__ == "__main__":
	main()
