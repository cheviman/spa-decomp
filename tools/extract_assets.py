"""
Name:        extract_assets.py
Description: the cartridge's binary files (the ones Valley Bell's disassembly includes whole) and the data the
             listing holds that has a form of its own, cut from the player's own cartridge dump, as they are and
             in forms one can edit, and the check that the edited forms build the cartridge's bytes back exactly
Version:     0.2.0
Created:     28-11-2026
Modified:    28-11-2026
Author:      Sebastian Toyos

license:BSD-3-Clause
The cartridge's binary files are the ones Valley Bell's disassembly includes whole (binclude), listed in
assets.txt (tools/listing_map.py writes it: ADDRESS LENGTH PATH LABEL, the address at 200000 in the
cartridge, so its byte at ADDRESS is the dump's offset ADDRESS - 0x200000). The dump is the file in rom/
whose CRC32 is 356F0849 or 8BD22145 and whose size is 2097152 (the World release, with its default save or
with the save area erased). Without --check, each file is written raw (raw/PATH), and in the form its kind
has, from the code that reads it (tools/forms/ has the text and WAV forms):
  - tile sets (.til: a count, then 16 bytes a tile) and the tile data with no count (the sprites' Tiles.bin,
    the levels' TileData.bin, art/*_Tiles.bin) as a PNG (tiles/PATH.png: 16 tiles a row, 4-bit indexed, the
    K2GE's order: row r is the little-endian 16-bit word at tile offset 2*r, pixel x (0 the left) is
    (word >> (14 - 2*x)) & 3); tiles.txt holds each set's count so the padding tiles are not part of it;
  - tile maps (.map) as text (maps/PATH.txt: width, height, offset, then the entries row by row);
  - sprites (.spr, read by CopySprites) as text (sprites/PATH.txt: the tile count, then each tile or column
    of tiles with its offset), and a picture of each sprite drawn from the sprites' tiles (sprites/PATH.png,
    index 0 see-through), which is not read back;
  - the levels' block layouts (BlkPlane1/2, as wide as the level's header says), block tile maps (a block a
    line), tile collision values, plane palette lists, and the hidden Sonic screen's tile map, as lines of
    16-bit words (words/PATH.txt);
  - the levels' object layouts (Objects.bin, read by LoadObjects) as a list a screen (objects/PATH.txt);
  - the SEGA voice (sound/SegaSound.bin, 8-bit unsigned PCM played by WAVE_OUT on timer 2 at 8000 Hz) as a WAV
    (sound/PATH.wav).
The listing's own data with a form: PalCollection (the palette lines every palette ID indexes, 3 colours of
0BGR a line, from its label to the next one in symbols.txt) as words, 3 a line (palettes/PalCollection.txt).
With --check, nothing is written: each file is built back from its form and compared with the dump's bytes
at its address (a tile set from its PNG and its count in tiles.txt, the rest from their text, WAV or raw
copy). A file missing, a picture of the wrong size or an index above 3, a text that does not parse, and any
byte that differs are each a failure, printed as PATH: what, at most 20 of them, then the count of each form
and of the failures. It exits 1 if there is any failure, else 0.
  py tools/extract_assets.py [--rom FILE] [--assets assets.txt] [--symbols symbols.txt] [--out assets] [--check]
"""
import argparse
import os
import re
import struct
import sys
import zlib

# Find the repository root (the folder that holds tools/core/) by walking up from this file's folder.
_d = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(_d, "tools", "core")):
	_d = os.path.dirname(_d)
sys.path.insert(0, os.path.join(_d, "tools", "core"))
sys.path.insert(0, os.path.join(_d, "tools"))
from asset_formats import write_png_indexed, read_png_indexed
from forms.sprite import sprite_to_text, sprite_from_text, sprite_picture
from forms.words import words_to_text, words_from_text
from forms.objects import objects_to_text, objects_from_text
from forms.wav import pcm_to_wav, wav_to_pcm

TILE_PALETTE = [(255, 255, 255), (170, 170, 170), (85, 85, 85), (0, 0, 0)]
ROM_SIZE = 2097152
ROM_CRC = (0x356F0849, 0x8BD22145)
CARTRIDGE_BASE = 0x200000
SEGA_VOICE_RATE = 8000  # timer 2 on T1 (the clock / 128, 48000 Hz) with TREG2 6, as WAVE_OUT sets it
HEADERLESS_TILES = re.compile(r"^(sprites/Tiles|level/.*_TileData|art/.*_Tiles)\.bin$")
LEVEL_WORDS = re.compile(r"^level/.*_(BlkPlane[12]|BlkTileMap|Coll|PalsPlane[12])\.bin$")
# The words a line of each kind of word file: a block's 4x4 tile map, 16 collision values, one palette ID (a
# plane's palette line each), the hidden Sonic screen's 20 tiles a row; a block layout is a level's row.
WORDS_WIDTH = {"BlkTileMap": 16, "Coll": 16, "PalsPlane1": 1, "PalsPlane2": 1}
OTHER_WORDS = {"art/HiddenSonic_TileMap.bin": 20}
# The listing's data with a form: label, the form's file, words a line.
LISTING_DATA = [("PalCollection", "palettes/PalCollection.txt", 3)]


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


def read_cartridge_symbols(path):
	"""The cartridge's labels of symbols.txt (func, code and data): a list of (address, name), by address."""
	symbols = []
	with open(path, encoding="latin-1") as f:
		for line in f:
			parts = line.split()
			if len(parts) >= 3 and not line.startswith("#") and parts[1] in ("func", "code", "data"):
				symbols.append((int(parts[0], 16), parts[2]))
	symbols.sort()
	return symbols


def listing_data_range(symbols, label):
	"""The address of label and the address of the next label after it, or None if it is not there."""
	for i, (address, name) in enumerate(symbols):
		if name == label:
			following = [a for a, _ in symbols[i + 1:] if a > address]
			return (address, following[0]) if following else None
	return None


def level_widths(rom, symbols):
	"""Each block layout's address mapped to its level's width in blocks, from the level headers (LvlHdr_*:
	u16 SizeX, SizeY, RingCount, then the pointers; the plane 2 layout's at 10, the plane 1 layout's at 26)."""
	widths = {}
	for address, name in symbols:
		if not name.startswith("LvlHdr_"):
			continue
		header = rom[address - CARTRIDGE_BASE:address - CARTRIDGE_BASE + 34]
		if len(header) < 34:
			continue
		size_x = struct.unpack_from("<H", header, 0)[0]
		for at in (10, 26):
			widths[struct.unpack_from("<I", header, at)[0]] = size_x
	return widths


def form_of(path):
	"""The form a file of assets.txt is kept in: tiles, map, sprite, words, objects, wav or raw."""
	if path.endswith(".til") or HEADERLESS_TILES.match(path):
		return "tiles"
	if path.endswith(".map"):
		return "map"
	if path.endswith(".spr"):
		return "sprite"
	if LEVEL_WORDS.match(path) or path in OTHER_WORDS:
		return "words"
	if path.endswith("_Objects.bin"):
		return "objects"
	if path == "sound/SegaSound.bin":
		return "wav"
	return "raw"


def form_path(out_dir, form, path):
	"""Where the form of the file at path is written."""
	return os.path.normpath(_form_path(out_dir, form, path))


def _form_path(out_dir, form, path):
	"""Where the form of the file at path is written, with the path's own slashes."""
	if form == "tiles":
		return os.path.join(out_dir, "tiles", path + ".png")
	if form == "map":
		return os.path.join(out_dir, "maps", path + ".txt")
	if form == "wav":
		return os.path.join(out_dir, "sound", path + ".wav")
	if form == "raw":
		return os.path.join(out_dir, "raw", path)
	return os.path.join(out_dir, form + "s" if form == "sprite" else form, path + ".txt")


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


def write_lines(path, lines):
	"""Write text lines to path, each ending in a newline, making its folder."""
	os.makedirs(os.path.dirname(path), exist_ok=True)
	with open(path, "w", encoding="latin-1", newline="\n") as f:
		f.write("\n".join(lines) + "\n")


def read_lines(path):
	"""The lines of a text file, without their newlines."""
	with open(path, encoding="latin-1") as f:
		return [line.rstrip("\r\n") for line in f]


def form_fits(form, path, data):
	"""Whether the bytes of a file fit the form of its kind (if not, the extraction keeps it only raw)."""
	if form == "tiles":
		if path.endswith(".til"):
			return build_tile_png(data) is not None
		return len(data) % 16 == 0 and 0 < len(data) // 16 <= 0xFFFF
	if form == "map":
		return build_map_text(data) is not None
	if form == "sprite":
		return sprite_to_text(data) is not None
	if form == "words":
		return words_to_text(data, 1) is not None
	if form == "objects":
		return objects_to_text(data) is not None
	return form == "wav"


def write_form(form, path, data, out_dir, widths, address, sprite_tiles):
	"""Write the form of one file; returns the tile count for tiles.txt, True for any other form written,
	or None when the data does not fit its form (and only the raw copy holds it)."""
	target = form_path(out_dir, form, path)
	if form == "tiles":
		headerless = not path.endswith(".til")
		if headerless and (len(data) % 16 or not 0 < len(data) // 16 <= 0xFFFF):
			return None
		result = build_tile_png(struct.pack("<H", len(data) // 16) + data if headerless else data)
		if not result:
			return None
		os.makedirs(os.path.dirname(target), exist_ok=True)
		write_png_indexed(target, result[0], TILE_PALETTE, 4)
		return result[1]
	if form == "map":
		lines = build_map_text(data)
	elif form == "sprite":
		lines = sprite_to_text(data)
		picture = sprite_picture(data, sprite_tiles) if lines is not None and sprite_tiles else None
		if picture:
			rows, left, top = picture
			png = os.path.join(out_dir, "sprites", path + ".png")
			os.makedirs(os.path.dirname(png), exist_ok=True)
			write_png_indexed(png, rows, TILE_PALETTE, 4, transparent=0)
			lines = [f"# picture {os.path.basename(png)}: its top left pixel is at ({left}, {top})"] + lines
	elif form == "words":
		kind = re.sub(r"^.*_", "", path)[:-4]
		width = OTHER_WORDS.get(path) or WORDS_WIDTH.get(kind) or widths.get(address, 16)
		lines = words_to_text(data, width, True)
	elif form == "objects":
		lines = objects_to_text(data)
	elif form == "wav":
		os.makedirs(os.path.dirname(target), exist_ok=True)
		with open(target, "wb") as f:
			f.write(pcm_to_wav(data, SEGA_VOICE_RATE))
		return True
	else:
		return None
	if lines is None:
		return None
	write_lines(target, lines)
	return True


def build_back(form, path, out_dir, tile_counts):
	"""The bytes the form of one file builds back, or a str saying why it cannot."""
	target = form_path(out_dir, form, path)
	if form == "tiles" and path not in tile_counts:
		return "no count in tiles.txt"
	if not os.path.exists(target):
		return f"missing {target}"
	if form == "tiles":
		try:
			rows, _ = read_png_indexed(target)
		except Exception as e:
			return str(e)
		built = build_tile_data(rows, tile_counts[path])
		if built is None:
			return "picture of the wrong size or an index above 3"
		return built if path.endswith(".til") else built[2:]
	if form == "raw":
		with open(target, "rb") as f:
			return f.read()
	if form == "wav":
		with open(target, "rb") as f:
			built = wav_to_pcm(f.read())
		return "not an 8-bit mono PCM WAV" if built is None else built
	lines = read_lines(target)
	built = {"map": build_map_data, "sprite": sprite_from_text, "words": words_from_text,
		"objects": objects_from_text}[form](lines)
	return f"the {form} text does not parse" if built is None else built


def compare(failures, path, built, expected):
	"""Add a failure for path if built (bytes, or a str saying why there are none) is not expected."""
	if isinstance(built, str):
		failures.append(f"{path}: {built}")
	elif built != expected:
		for i in range(min(len(built), len(expected))):
			if built[i] != expected[i]:
				failures.append(f"{path}: byte {i} differs")
				break
		else:
			failures.append(f"{path}: length differs")


def main():
	parser = argparse.ArgumentParser(description="The cartridge's binary files cut from the dump, and the check that the edited forms build the bytes back.")
	parser.add_argument("--rom", help="the cartridge dump")
	parser.add_argument("--assets", default=None, help="the assets list (default: the repository's assets.txt)")
	parser.add_argument("--symbols", default=None, help="the symbols (default: the repository's symbols.txt)")
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
	symbols_path = args.symbols or os.path.join(root, "symbols.txt")
	out_dir = args.out or os.path.join(root, "assets")

	with open(rom_path, "rb") as f:
		rom = f.read()
	entries = read_assets(assets_path)
	symbols = read_cartridge_symbols(symbols_path)
	listing = []
	for label, target, width in LISTING_DATA:
		span = listing_data_range(symbols, label)
		if span is None:
			print(f"{label} is not in {symbols_path}", file=sys.stderr)
			sys.exit(1)
		listing.append((label, span[0], span[1] - span[0], target, width))

	if args.check:
		tile_counts = {}
		tiles_txt_path = os.path.join(out_dir, "tiles.txt")
		if os.path.exists(tiles_txt_path):
			for line in read_lines(tiles_txt_path):
				parts = line.split()
				if len(parts) == 2:
					tile_counts[parts[0]] = int(parts[1])
		failures = []
		counts = {}
		for address, length, path, label in entries:
			offset = address - CARTRIDGE_BASE
			expected = rom[offset:offset + length]
			if len(expected) != length:
				failures.append(f"{path}: dump shorter than {length} bytes at {address:06X}")
				continue
			form = form_of(path)
			# A file whose bytes do not fit its form is kept only raw, as the extraction wrote it: decided
			# from the dump's bytes, so a form that is missing is a failure, not a fall back to the raw copy.
			if not form_fits(form, path, expected):
				form = "raw"
			counts[form] = counts.get(form, 0) + 1
			compare(failures, path, build_back(form, path, out_dir, tile_counts), expected)
		for label, address, length, target, width in listing:
			counts["listing"] = counts.get("listing", 0) + 1
			path = os.path.join(out_dir, target)
			built = words_from_text(read_lines(path)) if os.path.exists(path) else f"missing {path}"
			compare(failures, label, "the words text does not parse" if built is None else built,
				rom[address - CARTRIDGE_BASE:address - CARTRIDGE_BASE + length])

		for failure in failures[:20]:
			print(failure)
		names = [("tiles", "tile sets"), ("map", "maps"), ("sprite", "sprites"), ("words", "word files"),
			("objects", "object layouts"), ("wav", "WAV"), ("listing", "listing data"), ("raw", "raw")]
		print("checked: " + ", ".join(f"{counts.get(k, 0)} {name}" for k, name in names) + f"; {len(failures)} failures")
		sys.exit(1 if failures else 0)

	widths = level_widths(rom, symbols)
	sprite_tiles = next((rom[a - CARTRIDGE_BASE:a - CARTRIDGE_BASE + n] for a, n, p, _ in entries
		if p == "sprites/Tiles.bin"), b"")
	tile_sets = []
	written = {}
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
		form = form_of(path)
		result = write_form(form, path, data, out_dir, widths, address, sprite_tiles)
		if result is None:
			raw_only.append(path)
			continue
		written[form] = written.get(form, 0) + 1
		if form == "tiles":
			tile_sets.append((path, result))
	for label, address, length, target, width in listing:
		lines = words_to_text(rom[address - CARTRIDGE_BASE:address - CARTRIDGE_BASE + length], width, True)
		write_lines(os.path.join(out_dir, target), [f"# {label}: {length // 6} palette lines of 3 colours (0BGR), "
			"the line's palette ID after the #"] + lines)

	tiles_txt_path = os.path.join(out_dir, "tiles.txt")
	os.makedirs(out_dir, exist_ok=True)
	with open(tiles_txt_path, "w", encoding="latin-1", newline="\n") as f:
		for path, n in tile_sets:
			f.write(f"{path} {n}\n")

	print(f"tile sets as PNG: {len(tile_sets)} ({sum(n for _, n in tile_sets)} tiles)")
	print(f"maps as text: {written.get('map', 0)}")
	print(f"sprites as text: {written.get('sprite', 0)}")
	print(f"word files as text: {written.get('words', 0)}")
	print(f"object layouts as text: {written.get('objects', 0)}")
	print(f"sounds as WAV: {written.get('wav', 0)}")
	print(f"listing data as text: {len(listing)} ({', '.join(label for label, *_ in listing)})")
	kinds = {}
	for path in raw_only:
		kind = os.path.splitext(path)[1] or "(none)"
		kinds[kind] = kinds.get(kind, 0) + 1
	print(f"raw only: {len(raw_only)} (" + ", ".join(f"{count} {kind}" for kind, count in sorted(kinds.items())) + ")")
	print(f"bytes in all: {total_bytes}")


if __name__ == "__main__":
	main()
