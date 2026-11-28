"""
Name:        listing_map.py
Description: a map of the cartridge's bytes in AS's listing (build/asm/Main.lst): each numbered line that places
             bytes in 200000-3FFFFF, its kind, label and crc32; the binary files the disassembly includes whole
             (binclude); the program symbols (functions, code and data labels, the registers, the RAMs and the
             video memory by the disassembly's IDA segments, constants) with their comments
Version:     0.1.0
Created:     28-11-2026
Modified:    28-11-2026
Author:      Sebastian Toyos

license:BSD-3-Clause
The listing is AS's, of Valley Bell's disassembly assembled with its asw (its labels are the original's
addresses: docs/plan.md, the first round). Every row's length is the next numbered line's address less its own
(AS shows no bytes of INS3 and binclude), so the rows cover 200000-3FFFFF with no gap and no overlap: every byte
of the cartridge is a line of the disassembly. It writes the map (build/, it holds crc32s of the game's bytes),
assets.txt (the binclude files: addresses, sizes and paths) and symbols.txt (names and comments), and with --rom
the rows whose bytes are not that dump's (docs/plan.md, the fourteenth round: five instructions AS encodes
otherwise, and the save area of a dump that has it erased).
  py tools/listing_map.py [--listing build/asm/Main.lst] [--map build/asm/cartridge_map.tsv]
                          [--symbols symbols.txt] [--assets assets.txt] [--rom FILE]
"""
import argparse
import re
import zlib

# MAME's TLCS-900 mnemonics (dasm900.cpp's s_mnemonic, but db); AS writes a word's operation with a w, and DI
MNEMONICS_BASE = """adc add and andcf bit bs1b bs1f call calr ccf chg cp cpd cpdw cpdr cpdrw cpi cpir cpirw cpiw
	cpl daa dec decf decw div divs djnz ei ex exts extz halt inc incf incw jp jr jrl ld lda ldc ldcf ldd lddr lddrw
	lddw ldf ldi ldir ldirw ldiw ldw ldx link max mdec1 mdec2 mdec4 minc1 minc2 minc4 mirr mul mula muls neg nop
	normal or orcf paa pop popw push pushw rcf res ret retd reti rl rlc rlcw rld rlw rr rrc rrcw rrd rrw sbc scc
	scf set sla slaw sll sllw sra sraw srl srlw stcf sub swi tset unlk xor xorcf zcf""".split()
MNEMONICS = set(MNEMONICS_BASE) | {mnemonic + "w" for mnemonic in MNEMONICS_BASE} | {"di"}
DATA_WORDS = {"db", "dw", "dd"}
CARTRIDGE = range(0x200000, 0x400000)

NUMBERED = re.compile(r"^\(\d+\)\s*\d+/\s*([0-9A-F]+) : (.*)$")
CONTINUATION = re.compile(r"^ {20}((?:[0-9A-F]{2} )+)\s*$")
BYTES = re.compile(r"^(?:[0-9A-F]{2} )+ *$")
LABEL = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):")

EXCLUDED_COMMENT_PATTERNS = [
	"S U B R O U T I N E",
	"End of function",
	"FUNCTION CHUNK",
	"Segment type",
	"Attributes:",
]


class Row:
	"""A numbered line that places bytes in the cartridge: where it starts, its length, its kind, its label, its
	bytes (for the crc32) or None (INS3 and binclude), and its source (the line number or the path)."""
	def __init__(self, address, length, kind, label, data, source):
		self.address = address
		self.length = length
		self.kind = kind
		self.label = label
		self.data = data
		self.source = source


# IDA's segments of the disassembly's definitions, and the kind each gives its names
SEGMENT_END = re.compile(r"^; end of '([A-Z_0-9]+)'")
SEGMENT_KINDS = {"CPUREG": "io", "WORK_RAM": "var", "BIOS_RAM": "bios", "Z80_RAM": "z80", "VREGS": "k2ge",
	"VRAM": "video"}


class Symbol:
	"""A label or a definition: its address, its kind, its name, and its comment."""
	def __init__(self, address, kind, name, comment):
		self.address = address
		self.kind = kind
		self.name = name
		self.comment = comment


def parse_listing(path):
	"""The rows of the map, the symbols, and the numbered-line records (for comment resolution)."""
	rows = []
	row_num_idx = []   # the index in numbered where each row was created
	symbols = []
	labels = []        # (address, name, numbered_index)
	numbered = []     # (address, line_number, has_bytes, is_macro, is_def, src_path, label_name, comment, raw_source)
	label, label_address = "?", None
	extendable = None
	unsegmented = []   # the definitions not yet closed by a segment's end, by their index in symbols
	with open(path, encoding="latin-1") as listing:
		for line_number, line in enumerate(listing, 1):
			line = line.rstrip("\r\n")
			if "symbol table (* = unused):" in line:
				break
			match = NUMBERED.match(line)
			if not match:
				more = CONTINUATION.match(line)
				if more and extendable is not None:
					extendable.data.extend(int(b, 16) for b in more.group(1).split())
				continue
			extendable = None
			address = int(match.group(1), 16)
			field, source = match.group(2)[:20], match.group(2)[20:]
			named = LABEL.match(source)
			label_name = None
			if named:
				label_name = named.group(1)
				label, label_address = label_name, address
				source = source[named.end():]
			# The definitions before a segment starts (in the macros' files) stay values
			if source.startswith("; Segment type:"):
				unsegmented = []
			segment = SEGMENT_END.search(source)
			if segment:
				for index in unsegmented:
					symbols[index].kind = SEGMENT_KINDS.get(segment.group(1), "const")
				unsegmented = []
			words = source.split(";")[0].split()
			word = words[0].lower() if words else ""
			comment = source[source.index(";") + 1:] if ";" in source else ""
			has_bytes = BYTES.match(field) is not None
			is_macro = field.startswith("(MACRO)")
			is_def = field.startswith("=")
			src_path = ""
			numbered.append((address, line_number, has_bytes, is_macro, is_def, src_path, label_name, comment, source))

			if address not in CARTRIDGE:
				continue

			if is_def:
				def_match = re.match(r"^=([0-9A-F]+)H", field)
				name_match = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=", source)
				if def_match and name_match:
					value = int(def_match.group(1), 16)
					name = name_match.group(1)
					# Its kind is the IDA segment it is in, which the next "; end of 'NAME'" closes; one in
					# no segment (the macros' files: offsets in objects, the scripts' operators) is a value
					kind = "const"
					unsegmented.append(len(symbols))
					# A definition's own comment, by the labels' rules: IDA's references left out
					own = re.sub(r"\s+", " ", comment).strip()
					symbols.append(Symbol(value, kind, name, "" if "XREF" in own else own))
			elif has_bytes and word in MNEMONICS:
				data = [int(b, 16) for b in field.split()]
				row = Row(address, 0, "code", label, data, line_number)
				extendable = row
				rows.append(row)
				row_num_idx.append(len(numbered) - 1)
			elif is_macro and word == "ins3":
				row = Row(address, 0, "code", label, None, line_number)
				rows.append(row)
				row_num_idx.append(len(numbered) - 1)
			elif word == "binclude":
				path_match = re.search(r'binclude\s+"([^"]+)"', source)
				src_path = path_match.group(1) if path_match else ""
				numbered[len(numbered) - 1] = (address, line_number, has_bytes, is_macro, is_def, src_path, label_name, comment, source)
				row = Row(address, 0, "binclude", label, None, src_path)
				rows.append(row)
				row_num_idx.append(len(numbered) - 1)
			elif has_bytes:
				data = [int(b, 16) for b in field.split()]
				row = Row(address, 0, "data", label, data, line_number)
				extendable = row
				rows.append(row)
				row_num_idx.append(len(numbered) - 1)

			if label_name:
				labels.append((address, label_name, len(numbered) - 1))

	# Resolve the length of every row: the address of the very next numbered line after it, less its own address
	for i, row in enumerate(rows):
		idx = row_num_idx[i]
		if idx + 1 < len(numbered):
			row.length = numbered[idx + 1][0] - row.address
		else:
			row.length = 0x400000 - row.address

	# Classify the labels as symbols
	instruction_starts = {row.address for row in rows if row.kind == "code"}
	for address, name, index in labels:
		if address not in CARTRIDGE:
			continue
		is_func = False
		for j in range(index - 1, -1, -1):
			a, ln, has_b, is_m, is_d, sp, ln_name, com, raw = numbered[j]
			if has_b or is_m or is_d:
				break
			if "S U B R O U T I N E" in com:
				is_func = True
				break
		if is_func:
			kind = "func"
		elif address in instruction_starts:
			kind = "code"
		else:
			kind = "data"
		symbols.append(Symbol(address, kind, name, ""))
	return rows, symbols, labels, numbered


def compute_comments(symbols, numbered, labels):
	"""Fill in the comments for the label symbols from the listing's comment lines."""
	comments = {}
	for address, name, index in labels:
		if address not in CARTRIDGE:
			continue
		full_comments = []
		for j in range(index - 1, -1, -1):
			a, ln, has_b, is_m, is_d, sp, ln_name, com, raw = numbered[j]
			if has_b or is_m or is_d:
				break
			if ln_name is not None:
				break
			stripped = com.strip()
			if not stripped:
				continue
			# The line must be a full-line comment: the source after the label (none here) is just "; text"
			# Valley Bell's comments start at the line's first column; the indented ones are IDA's lists of
			# more references, and comments of the instructions
			if not raw.startswith(";"):
				continue
			# Apply exclusion rules
			excluded = False
			for pattern in EXCLUDED_COMMENT_PATTERNS:
				if pattern in stripped:
					excluded = True
					break
			if "XREF" in stripped:
				excluded = True
			if stripped.startswith("\t") or stripped.startswith("    "):
				# Indented comment lines (IDA's XREF continuation)
				excluded = True
			if stripped.startswith("=") or stripped.startswith("-"):
				excluded = True
			if not excluded:
				full_comments.append(stripped)
		# The label line's own comment
		own_comment = numbered[index][7].strip()
		all_parts = full_comments[::-1]
		if own_comment:
			all_parts.append(own_comment)
		# Filter each part
		filtered = []
		for c in all_parts:
			excluded = False
			for pattern in EXCLUDED_COMMENT_PATTERNS:
				if pattern in c:
					excluded = True
					break
			if "XREF" in c:
				excluded = True
			if c.startswith("\t") or c.startswith("    "):
				excluded = True
			if c.startswith("=") or c.startswith("-"):
				excluded = True
			# IDA's segment lines and the directives it left commented out
			if c.startswith("org ") or c.startswith("end of '"):
				excluded = True
			if not excluded:
				filtered.append(c)
		joined = " ".join(filtered)
		joined = re.sub(r"\s+", " ", joined).strip()
		joined = joined.lstrip(";").strip()
		comments[(address, name)] = joined
	# Update the label symbols
	for symbol in symbols:
		if symbol.kind in ("func", "code", "data"):
			key = (symbol.address, symbol.name)
			if key in comments:
				symbol.comment = comments[key]


def compare_with_rom(rows, path):
	"""The rows whose bytes as the listing shows them are not the dump's: those in the flash's save area
	(3F8000-3FBFFF, which the disassembly fills with the game's default save and a dump may hold erased) counted
	apart, the others listed; and the rows it cannot compare (INS3 and binclude, whose bytes the listing does
	not show: extract_assets.py --check compares the binclude files)."""
	rom = open(path, "rb").read()
	if len(rom) != 0x200000:
		print(f"{path}: {len(rom)} bytes, not a 2 MB cartridge")
		return
	unshown = 0
	in_save = [0, 0]
	others = []
	for row in rows:
		if row.data is None or len(row.data) != row.length:
			unshown += 1
			continue
		dump = rom[row.address - 0x200000:row.address - 0x200000 + row.length]
		if dump == bytes(row.data):
			continue
		if 0x3F8000 <= row.address < 0x3FC000:
			in_save[0] += 1
			in_save[1] += sum(1 for a, b in zip(dump, row.data) if a != b)
		else:
			others.append(row)
	print(f"against {path}: {len(others)} rows differ outside the save area, {in_save[0]} in it "
		f"({in_save[1]} bytes); {unshown} rows not shown in the listing")
	for row in others:
		print(f"  differs {row.address:06X}+{row.length} {row.kind} under {row.label} (line {row.source})")


def main():
	parser = argparse.ArgumentParser(description="A map of the cartridge's bytes in AS's listing.")
	parser.add_argument("--listing", default="build/asm/Main.lst", help="AS's listing of the disassembly")
	parser.add_argument("--map", default="build/asm/cartridge_map.tsv", help="the map of the cartridge's bytes")
	parser.add_argument("--symbols", default="symbols.txt", help="the program symbols")
	parser.add_argument("--assets", default="assets.txt", help="the binary files the disassembly includes")
	parser.add_argument("--rom", help="a cartridge dump to compare the listing's bytes with, row by row")
	args = parser.parse_args()

	rows, symbols, labels, numbered = parse_listing(args.listing)
	compute_comments(symbols, numbered, labels)

	# Write the map
	with open(args.map, "w", encoding="utf-8", newline="\n") as out:
		out.write("# start\tlength\tkind\tlabel\tcrc32\tsource\n")
		for row in rows:
			crc = "-" if row.data is None or len(row.data) != row.length else "%08X" % zlib.crc32(bytes(row.data))
			out.write(f"{row.address:06X}\t{row.length}\t{row.kind}\t{row.label}\t{crc}\t{row.source}\n")

	# Write the assets
	with open(args.assets, "w", encoding="utf-8", newline="\n") as out:
		out.write("# Sonic Pocket Adventure (Neo Geo Pocket Color, World) - the cartridge's binary files\n")
		out.write("#\n")
		out.write("# Addresses and sizes only: no game data lives in this file. Each line is a file Valley Bell's disassembly\n")
		out.write("# includes whole (binclude): where it sits in the cartridge, its size in bytes, its path in the disassembly\n")
		out.write("# and the label at its start. tools/listing_map.py writes it from AS's listing.\n")
		out.write("# Format:  ADDRESS  LENGTH  PATH  LABEL\n")
		for row in rows:
			if row.kind == "binclude":
				lbl = row.label if row.label != "?" else "-"
				out.write(f"{row.address:06X}  {row.length}  {row.source}  {lbl}\n")

	# Write the symbols
	with open(args.symbols, "w", encoding="utf-8", newline="\n") as out:
		out.write("# Sonic Pocket Adventure (Neo Geo Pocket Color, World) - TLCS-900/H program symbols\n")
		out.write("#\n")
		out.write("# Addresses and names only: no game data lives in this file.\n")
		out.write("# Format:  ADDRESS  KIND  NAME   [# comment]\n")
		out.write("#   KIND: func = function entry, code = code label, data = data label (the cartridge, 200000-3FFFFF);\n")
		out.write("#         io = a register of the TMP95C061 and the console's ports (00-FF), var = the game's work RAM\n")
		out.write("#         (4000-6BFF), bios = the BIOS's work RAM (6C00-6FFF), z80 = the Z80's RAM (7000-7FFF), k2ge = the\n")
		out.write("#         K2GE's registers and palettes, video = its sprite, map and tile memory, const = a value (the\n")
		out.write("#         disassembly's IDA segments: CPUREG, WORK_RAM, BIOS_RAM, Z80_RAM, VREGS, VRAM; const outside them)\n")
		out.write("# The names and comments are Valley Bell's disassembly's (IDA's names where it kept them), written from\n")
		out.write("# AS's listing by tools/listing_map.py.\n")
		out.write("\n")
		sections = [
			("functions", "func"),
			("code labels", "code"),
			("data labels", "data"),
			("I/O registers", "io"),
			("work RAM", "var"),
			("the BIOS's work RAM", "bios"),
			("the Z80's RAM", "z80"),
			("the K2GE's registers", "k2ge"),
			("video memory", "video"),
			("constants", "const"),
		]
		for name, kind in sections:
			section_symbols = [s for s in symbols if s.kind == kind]
			if not section_symbols:
				continue
			out.write(f"# ======== {name} ========\n")
			out.write("\n")
			for symbol in section_symbols:
				line = f"{symbol.address:06X}  {symbol.kind}  {symbol.name}"
				if symbol.comment:
					line += f"  # {symbol.comment}"
				out.write(line + "\n")
			out.write("\n")

	# Stdout summary
	by_kind = {}
	for row in rows:
		count, total = by_kind.get(row.kind, (0, 0))
		by_kind[row.kind] = (count + 1, total + row.length)
	for kind in ("code", "data", "binclude"):
		if kind in by_kind:
			count, total = by_kind[kind]
			print(f"{kind}: {count} rows, {total} bytes")
	total_bytes = sum(row.length for row in rows)
	print(f"total: {total_bytes} bytes")

	# Gaps and overlaps
	gaps = []
	overlaps = []
	prev_end = 0x200000
	for row in rows:
		if row.address > prev_end:
			gaps.append((prev_end, row.address - 1))
		if row.address < prev_end:
			overlaps.append((row.address, prev_end))
		prev_end = max(prev_end, row.address + row.length)
	if prev_end < 0x400000:
		gaps.append((prev_end, 0x3FFFFF))
	for start, end in gaps:
		print(f"gap {start:06X}-{end:06X}")
	for start, end in overlaps:
		print(f"overlap {start:06X}-{end:06X}")

	symbol_counts = {}
	for symbol in symbols:
		symbol_counts[symbol.kind] = symbol_counts.get(symbol.kind, 0) + 1
	for kind in ("func", "code", "data", "io", "var", "bios", "z80", "k2ge", "video", "const"):
		if kind in symbol_counts:
			print(f"{kind}: {symbol_counts[kind]} symbols")

	if args.rom:
		compare_with_rom(rows, args.rom)

	exit(1 if gaps or overlaps else 0)


if __name__ == "__main__":
	main()
