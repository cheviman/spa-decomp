"""
Name:        script.py
Description: the scripts and tables the game reads from the listing's data (animation, hit boxes, special stage,
             boss 6; objects, collision lines, the level table and headers) as a command a line, and back
Version:     0.1.0
Created:     28-11-2026
Modified:    28-11-2026
Author:      Sebastian Toyos

license:BSD-3-Clause
This module converts a run of the cartridge's scripts and tables (Sonic Pocket Adventure, Neo Geo Pocket Color)
into an editable text form and back. It covers the script readers the game uses: DoAnimScript (animation
scripts), CheckCollision (hit box lists), DoSpcStgScript (special stage scripts) and DoBoss6Script /
DoBoss6sScript (boss 6's scripts), and the tables of fixed rows it reads: the objects' definitions
(InitializeObj), the tile collision lines (GetCollValue), LevelTable's entries and the level headers. A run is a
section a label ("KIND NAME"), then a command a line by the disassembly's macro name, its operands by name where
they have one (a label, a sprite file, an object field, an operator, a tube direction), the bytes no reader takes
as "bytes" lines. The conversion is table-driven: every command is described in the COMMANDS table and is
decoded and encoded by one generic piece of code.
"""

import re

COMMANDS = {
	# keyword: (section kind, prefix bytes, operand kinds)
	"asEnd": ("script", b"\x00", []),
	"asSpriteWait": ("script", b"\x01", ["u8d", "sprite"]),
	"asJump": ("script", b"\x02", ["target"]),
	"asWait": ("script", b"\x03", ["u8d"]),
	"asPosSprite": ("script", b"\x04", ["u8x", "sprite", "s8d", "s8d"]),
	"asWriteByte": ("script", b"\x05", ["ofs", "u8x"]),
	"asWriteWord": ("script", b"\x06", ["ofs", "u16x"]),
	"asWriteLong": ("script", b"\x07", ["ofs", "long"]),
	"asFrameIndex": ("script", b"\x08", ["ofs", "u8d"]),
	"asCall": ("script", b"\x09", ["target"]),
	"asCondJump": ("script", b"\x0A", ["ofs", "op", "u8x", "target"]),
	"asPlaySound": ("script", b"\x0B", ["u16x"]),
	"asPlrSprite": ("script", b"\x0C", ["u8x", "u16x"]),
	"asPalette": ("script", b"\x0D", ["u8x", "u16x"]),
	"asSpriteFlag": ("script", b"\x0E", ["u8x", "sprite"]),
	"HitBoxData": ("hitbox", b"", ["s8d", "s8d", "u8d", "u8d"]),
	"HitBoxEnd": ("hitbox", b"\x80\x80", []),
	"ssWait": ("spcstg", b"\x00", ["u8d"]),
	"ssTubeDir": ("spcstg", b"\x01", ["dir"]),
	"ssRing": ("spcstg", b"\x02", ["u8x"]),
	"ssRingWait": ("spcstg", b"\x03", ["u8x", "u16d"]),
	"ssBomb": ("spcstg", b"\x04", ["u8x"]),
	"ssBombWait": ("spcstg", b"\x05", ["u8x", "u16d"]),
	"ssFlower": ("spcstg", b"\x06", ["u8x"]),
	"ssFlowerWait": ("spcstg", b"\x07", ["u8x", "u16d"]),
	"ssJump": ("spcstg", b"\x08", ["target"]),
	"ssCheckpoint": ("spcstg", b"\x09", ["u8d"]),
	"ssEnd": ("spcstg", b"\x0A\x00", []),
	"ssCall": ("spcstg", b"\x0B", ["target"]),
	"ssReturn": ("spcstg", b"\x0C\x00", []),
	"ssInit": ("spcstg", b"\xFF", ["u8d"]),
	"sb6Command": ("boss6", b"", ["u7d", "u8d", "u8d"]),
	"sb6PlaySound": ("boss6", b"\xF4", ["u16x"]),
	"sb6_F5": ("boss6", b"\xF5", []),
	"sb6_Write4A": ("boss6", b"\xF6", ["u8d"]),
	"sb6_FC": ("boss6", b"\xFC", []),
	"sb6_FD": ("boss6", b"\xFD", []),
	"sb6sCommand": ("boss6spin", b"", ["u7d", "u8x"]),
	"sb6sPlaySound": ("boss6spin", b"\xF5", ["u16x"]),
	"sb6sAtkBox": ("boss6spin", b"\xF6", ["target"]),
	"sb6sJump": ("boss6spin", b"\xFE", ["target"]),
	"sb6sEnd": ("boss6spin", b"\xFF", []),
	"Object": ("object", b"", ["target", "target", "u16x", "u8x", "u8x"]),
	"CollisonDef": ("collision", b"", ["s8d", "s8d", "long", "long"]),
	"LevelStruct": ("level", b"", ["long", "long", "u16x", "u16x", "u16x"]),
	"LevelHeader": ("lvlhdr", b"", ["u16d", "u16d", "u16d", "long", "long", "long", "long", "long", "long", "long"]),
}

_KNDS = ("script", "hitbox", "spcstg", "boss6", "boss6spin", "object", "collision", "level", "lvlhdr")
_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_DEC_RE = re.compile(r"^-?[0-9]+$")
_HEX_RE = re.compile(r"^0[xX][0-9A-Fa-f]+$")
_OF_NAMES = {0x0E: "objPriority", 0x14: "objSprFlags", 0x2E: "objBdyBox", 0x32: "objAtkBox"}
_OP_NAMES = {0: "GT", 1: "GE", 2: "LT", 3: "LE", 4: "UGT", 5: "UGE", 6: "ULT", 7: "ULE", 8: "EQ", 9: "NE"}
_DIR_NAMES = {0: "ssTubeStraight", 1: "ssTubeRight", 2: "ssTubeLeft", 3: "ssTubeUp", 4: "ssTubeDown"}


def _op_size(kind):
	# Returns the number of bytes one operand of the given kind occupies.
	if kind in ("u8d", "u7d", "s8d", "u8x", "ofs", "op", "dir"):
		return 1
	if kind in ("u16d", "u16x", "sprite"):
		return 2
	if kind == "target":
		return 3
	if kind == "long":
		return 4
	return 0


def _cmd_len(kw):
	# Returns the total length in bytes of the command with the given keyword.
	_, prefix, ops = COMMANDS[kw]
	return len(prefix) + sum(_op_size(o) for o in ops)


def _enc_operand(kind, v, extra):
	# Encodes one operand value into its text token.
	if kind in ("u8d", "u7d", "s8d", "u16d"):
		return str(v)
	if kind == "u8x":
		return "0x%02X" % v
	if kind == "u16x":
		return "0x%04X" % v
	if kind == "ofs":
		return _OF_NAMES.get(v, "0x%02X" % v)
	if kind == "op":
		return _OP_NAMES.get(v, "0x%02X" % v)
	if kind == "dir":
		return _DIR_NAMES.get(v, "0x%02X" % v)
	if kind == "sprite":
		return extra["sprites"].get(0x200000 + v, "0x%04X" % v)
	if kind == "target":
		if v in extra["sections"]:
			return extra["sections"][v]
		return extra["names"].get(v, "0x%06X" % v)
	if kind == "long":
		if v in extra["sections"]:
			return extra["sections"][v]
		return extra["names"].get(v, "0x%08X" % v)
	return str(v)


def _dec_num(kind, tok):
	# Parses a numeric token for the given operand kind, or returns None.
	if _DEC_RE.match(tok):
		v = int(tok)
		if kind in ("u8d", "u8x", "ofs", "op", "dir"):
			return v if 0 <= v <= 255 else None
		if kind == "u7d":
			return v if 0 <= v <= 127 else None
		if kind == "s8d":
			return v if -128 <= v <= 127 else None
		if kind in ("u16d", "u16x", "sprite"):
			return v if 0 <= v <= 65535 else None
		if kind == "target":
			return v if 0 <= v <= 0xFFFFFF else None
		if kind == "long":
			return v if 0 <= v <= 0xFFFFFFFF else None
		return None
	if _HEX_RE.match(tok):
		v = int(tok, 16)
		if kind in ("u8d", "u8x", "ofs", "op", "dir"):
			return v if 0 <= v <= 255 else None
		if kind == "u7d":
			return v if 0 <= v <= 127 else None
		if kind == "s8d":
			return v if -128 <= v <= 127 else None
		if kind in ("u16d", "u16x", "sprite"):
			return v if 0 <= v <= 65535 else None
		if kind == "target":
			return v if 0 <= v <= 0xFFFFFF else None
		if kind == "long":
			return v if 0 <= v <= 0xFFFFFFFF else None
		return None
	return None


def _dec_operand(kind, tok, extra):
	# Decodes one operand token into its value, or returns None.
	if kind in ("u8d", "u7d", "s8d", "u16d"):
		return _dec_num(kind, tok)
	if kind in ("u8x", "u16x"):
		return _dec_num(kind, tok)
	if kind == "ofs":
		for v, n in _OF_NAMES.items():
			if tok == n:
				return v
		return _dec_num("u8x", tok)
	if kind == "op":
		for v, n in _OP_NAMES.items():
			if tok == n:
				return v
		return _dec_num("u8x", tok)
	if kind == "dir":
		for v, n in _DIR_NAMES.items():
			if tok == n:
				return v
		return _dec_num("u8x", tok)
	if kind == "sprite":
		if tok in extra["sprites"]:
			a = extra["sprites"][tok]
			if 0 <= a - 0x200000 <= 0xFFFF:
				return a - 0x200000
			return None
		return _dec_num("u16x", tok)
	if kind == "target":
		if tok in extra["sections"]:
			a = extra["sections"][tok]
			return a if 0 <= a <= 0xFFFFFF else None
		if tok in extra["addresses"]:
			a = extra["addresses"][tok]
			return a if 0 <= a <= 0xFFFFFF else None
		return _dec_num("target", tok)
	if kind == "long":
		if tok in extra["sections"]:
			a = extra["sections"][tok]
			return a if 0 <= a <= 0xFFFFFFFF else None
		if tok in extra["addresses"]:
			a = extra["addresses"][tok]
			return a if 0 <= a <= 0xFFFFFFFF else None
		return _dec_num("long", tok)
	return None


def _enc_operand_bytes(kind, v):
	# Encodes one operand value into its little-endian byte string.
	if kind in ("u8d", "u7d", "s8d", "u8x", "ofs", "op", "dir"):
		return bytes([v & 0xFF])
	if kind in ("u16d", "u16x", "sprite"):
		return bytes([v & 0xFF, (v >> 8) & 0xFF])
	if kind == "target":
		return bytes([v & 0xFF, (v >> 8) & 0xFF, (v >> 16) & 0xFF])
	if kind == "long":
		return bytes([v & 0xFF, (v >> 8) & 0xFF, (v >> 16) & 0xFF, (v >> 24) & 0xFF])
	return b""


def _dec_operand_bytes(kind, b):
	# Decodes a little-endian byte string into an operand value of the given kind.
	if kind in ("u8d", "u8x", "ofs", "op", "dir"):
		return b[0]
	if kind == "u7d":
		return b[0] if b[0] <= 127 else None
	if kind == "s8d":
		return b[0] if b[0] < 128 else b[0] - 256
	if kind in ("u16d", "u16x", "sprite"):
		return b[0] | (b[1] << 8)
	if kind == "target":
		return b[0] | (b[1] << 8) | (b[2] << 16)
	if kind == "long":
		return b[0] | (b[1] << 8) | (b[2] << 16) | (b[3] << 24)
	return None


def _find_cmd(kind, data, p, end, first):
	# Returns the keyword of the command matching at position p in the given section kind, or None.
	if kind == "hitbox":
		if not first and p + 2 <= end and data[p] == 0x80 and data[p + 1] == 0x80:
			return "HitBoxEnd"
		if p + 4 <= end:
			return "HitBoxData"
		return None
	if kind == "boss6":
		if p + 3 <= end and data[p] < 0x80:
			return "sb6Command"
		for kw, (k, prefix, ops) in COMMANDS.items():
			if k != kind or not prefix:
				continue
			l = len(prefix) + sum(_op_size(o) for o in ops)
			if p + l > end:
				continue
			if data[p:p + len(prefix)] == prefix:
				return kw
		return None
	if kind == "boss6spin":
		if p + 2 <= end and data[p] < 0x80:
			return "sb6sCommand"
		for kw, (k, prefix, ops) in COMMANDS.items():
			if k != kind or not prefix:
				continue
			l = len(prefix) + sum(_op_size(o) for o in ops)
			if p + l > end:
				continue
			if data[p:p + len(prefix)] == prefix:
				return kw
		return None
	for kw, (k, prefix, ops) in COMMANDS.items():
		if k != kind:
			continue
		l = len(prefix) + sum(_op_size(o) for o in ops)
		if p + l > end:
			continue
		if prefix and data[p:p + len(prefix)] == prefix:
			return kw
	return None


def _bytes_lines(data, p, end):
	# Returns the list of bytes lines for the data from p to end.
	lines = []
	while p < end:
		chunk = data[p:min(p + 16, end)]
		toks = ["0x%02X" % b for b in chunk]
		lines.append("\tbytes " + " ".join(toks))
		p += 16
	return lines


def _decode_row(kw, data, p, end, extra):
	# Decodes one row of the given command at position p, returning the list of tokens or None.
	_, _, ops = COMMANDS[kw]
	toks = [kw]
	off = p + len(COMMANDS[kw][1])
	for o in ops:
		v = _dec_operand_bytes(o, data[off:off + _op_size(o)])
		if v is None:
			return None
		toks.append(_enc_operand(o, v, extra))
		off += _op_size(o)
	return toks


def script_to_text(data, base, sections, names, sprites):
	# Converts a run of cartridge scripts into a list of text lines, or None if the input is invalid.
	if not data or not sections:
		return None
	if sections[0][0] != base:
		return None
	seen = set()
	for addr, name, kind in sections:
		if not (base <= addr < base + len(data)):
			return None
		if kind not in _KNDS:
			return None
		if not _NAME_RE.match(name):
			return None
		if name in seen:
			return None
		seen.add(name)
	for i in range(1, len(sections)):
		if sections[i][0] <= sections[i - 1][0]:
			return None
	sections_map = {}
	for addr, name, kind in sections:
		sections_map[addr] = name
	extra = {"sprites": sprites, "names": names, "sections": sections_map}
	lines = []
	for i, (addr, name, kind) in enumerate(sections):
		start = addr - base
		if i + 1 < len(sections):
			end = sections[i + 1][0] - base
		else:
			end = len(data)
		lines.append(kind + " " + name)
		p = start
		if kind == "script":
			while p < end:
				kw = _find_cmd("script", data, p, end, True)
				if kw is None:
					lines.extend(_bytes_lines(data, p, end))
					break
				_, _, ops = COMMANDS[kw]
				toks = [kw]
				off = p + len(COMMANDS[kw][1])
				ok = True
				for o in ops:
					v = _dec_operand_bytes(o, data[off:off + _op_size(o)])
					if v is None:
						ok = False
						break
					toks.append(_enc_operand(o, v, extra))
					off += _op_size(o)
				if not ok:
					lines.extend(_bytes_lines(data, p, end))
					break
				lines.append("\t" + " ".join(toks))
				p += _cmd_len(kw)
				if kw == "asFrameIndex":
					n = data[p - 1]
					if n > 0:
						entries_ok = False
						if p < end:
							if data[p] == 0x0E:
								entry_kw = "asSpriteFlag"
								entry_size = 4
							else:
								entry_kw = "asPosSprite"
								entry_size = 6
							if p + n * entry_size <= end:
								entries_ok = True
								for j in range(n):
									ep = p + j * entry_size
									expected_op = 0x0E if entry_kw == "asSpriteFlag" else 0x04
									if data[ep] != expected_op:
										entries_ok = False
										break
						if entries_ok:
							for j in range(n):
								ep = p + j * entry_size
								_, _, e_ops = COMMANDS[entry_kw]
								e_kw = entry_kw
								e_toks = [e_kw]
								e_off = ep + 1
								ok_e = True
								for e_o in e_ops:
									e_v = _dec_operand_bytes(e_o, data[e_off:e_off + _op_size(e_o)])
									if e_v is None:
										ok_e = False
										break
									e_toks.append(_enc_operand(e_o, e_v, extra))
									e_off += _op_size(e_o)
								if not ok_e:
									break
								lines.append("\t\t" + " ".join(e_toks))
							p += n * entry_size
							continue
						else:
							lines.pop()
							lines.extend(_bytes_lines(data, p - _cmd_len("asFrameIndex"), end))
							break
					else:
						continue
				if kw in ("asEnd", "asJump"):
					if p < end:
						lines.extend(_bytes_lines(data, p, end))
					break
				continue
		elif kind == "hitbox":
			first = True
			while p < end:
				kw = _find_cmd("hitbox", data, p, end, first)
				if kw is None:
					lines.extend(_bytes_lines(data, p, end))
					break
				_, _, ops = COMMANDS[kw]
				toks = [kw]
				off = p + len(COMMANDS[kw][1])
				ok = True
				for o in ops:
					v = _dec_operand_bytes(o, data[off:off + _op_size(o)])
					if v is None:
						ok = False
						break
					toks.append(_enc_operand(o, v, extra))
					off += _op_size(o)
				if not ok:
					lines.extend(_bytes_lines(data, p, end))
					break
				lines.append("\t" + " ".join(toks))
				p += _cmd_len(kw)
				if kw == "HitBoxEnd":
					first = True
					if end - p < 6:
						if p < end:
							lines.extend(_bytes_lines(data, p, end))
						break
				else:
					first = False
				continue
		elif kind == "spcstg":
			while p < end:
				kw = _find_cmd("spcstg", data, p, end, True)
				if kw is None:
					lines.extend(_bytes_lines(data, p, end))
					break
				_, _, ops = COMMANDS[kw]
				toks = [kw]
				off = p + len(COMMANDS[kw][1])
				ok = True
				for o in ops:
					v = _dec_operand_bytes(o, data[off:off + _op_size(o)])
					if v is None:
						ok = False
						break
					toks.append(_enc_operand(o, v, extra))
					off += _op_size(o)
				if not ok:
					lines.extend(_bytes_lines(data, p, end))
					break
				lines.append("\t" + " ".join(toks))
				p += _cmd_len(kw)
				continue
		elif kind in ("boss6", "boss6spin"):
			while p < end:
				kw = _find_cmd(kind, data, p, end, True)
				if kw is None:
					lines.extend(_bytes_lines(data, p, end))
					break
				_, _, ops = COMMANDS[kw]
				toks = [kw]
				off = p + len(COMMANDS[kw][1])
				ok = True
				for o in ops:
					v = _dec_operand_bytes(o, data[off:off + _op_size(o)])
					if v is None:
						ok = False
						break
					toks.append(_enc_operand(o, v, extra))
					off += _op_size(o)
				if not ok:
					lines.extend(_bytes_lines(data, p, end))
					break
				lines.append("\t" + " ".join(toks))
				p += _cmd_len(kw)
				continue
		elif kind == "object":
			kw = "Object"
			l = _cmd_len(kw)
			if p + l <= end:
				toks = _decode_row(kw, data, p, end, extra)
				if toks is not None:
					lines.append("\t" + " ".join(toks))
					p += l
			if p < end:
				lines.extend(_bytes_lines(data, p, end))
		elif kind == "lvlhdr":
			kw = "LevelHeader"
			l = _cmd_len(kw)
			if p + l <= end:
				toks = _decode_row(kw, data, p, end, extra)
				if toks is not None:
					lines.append("\t" + " ".join(toks))
					p += l
			if p < end:
				lines.extend(_bytes_lines(data, p, end))
		elif kind == "collision":
			kw = "CollisonDef"
			l = _cmd_len(kw)
			while p + l <= end:
				toks = _decode_row(kw, data, p, end, extra)
				if toks is None:
					break
				lines.append("\t" + " ".join(toks))
				p += l
			if p < end:
				lines.extend(_bytes_lines(data, p, end))
		elif kind == "level":
			kw = "LevelStruct"
			l = _cmd_len(kw)
			while p + l <= end:
				toks = _decode_row(kw, data, p, end, extra)
				if toks is None:
					break
				lines.append("\t" + " ".join(toks))
				p += l
			if p < end:
				lines.extend(_bytes_lines(data, p, end))
	addresses = {}
	for addr, name, kind in sections:
		addresses[name] = addr
	for addr, name in names.items():
		addresses[name] = addr
	inverse = {path: addr for addr, path in sprites.items()}
	result = script_from_text(lines, base, addresses, inverse)
	if result != data:
		return None
	return lines


def script_from_text(lines, base, addresses, sprites):
	# Converts a list of text lines back into the original script bytes, or None if the input is invalid.
	if not isinstance(lines, list):
		return None
	cleaned = []
	for line in lines:
		if not isinstance(line, str):
			return None
		idx = line.find("#")
		if idx >= 0:
			line = line[:idx]
		toks = line.split()
		if toks:
			cleaned.append(toks)
	if not cleaned:
		return None
	# The first line must be a section header.
	if len(cleaned[0]) != 2 or cleaned[0][0] not in _KNDS:
		return None
	# Determine the length of each line in bytes.
	line_lens = []
	for toks in cleaned:
		if len(toks) == 2 and toks[0] in _KNDS:
			line_lens.append(0)
		elif toks[0] == "bytes":
			if len(toks) < 2:
				return None
			for t in toks[1:]:
				if _HEX_RE.match(t):
					v = int(t, 16)
				elif _DEC_RE.match(t):
					v = int(t)
				else:
					return None
				if not (0 <= v <= 255):
					return None
			line_lens.append(len(toks) - 1)
		elif toks[0] in COMMANDS:
			kw = toks[0]
			_, _, ops = COMMANDS[kw]
			if len(toks) != 1 + len(ops):
				return None
			line_lens.append(_cmd_len(kw))
		else:
			return None
	# Compute section addresses from the text layout.
	section_addrs = {}
	offset = 0
	for idx, toks in enumerate(cleaned):
		if len(toks) == 2 and toks[0] in _KNDS:
			kind, name = toks
			if not _NAME_RE.match(name):
				return None
			if name in section_addrs:
				return None
			section_addrs[name] = base + offset
		offset += line_lens[idx]
	# Encode all lines into bytes.
	extra = {"sprites": sprites, "addresses": addresses, "sections": section_addrs}
	out = bytearray()
	for idx, toks in enumerate(cleaned):
		if len(toks) == 2 and toks[0] in _KNDS:
			continue
		if toks[0] == "bytes":
			for t in toks[1:]:
				if _HEX_RE.match(t):
					v = int(t, 16)
				else:
					v = int(t)
				out.append(v)
			continue
		kw = toks[0]
		_, prefix, ops = COMMANDS[kw]
		out.extend(prefix)
		for j, o in enumerate(ops):
			v = _dec_operand(o, toks[1 + j], extra)
			if v is None:
				return None
			out.extend(_enc_operand_bytes(o, v))
	return bytes(out)
