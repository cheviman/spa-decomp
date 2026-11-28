"""
Name:        objects.py
Description: a level's object layout (Objects.bin, read by LoadObjects) as text, a list a screen
Version:     0.1.0
Created:     28-11-2026
Modified:    28-11-2026
Author:      Sebastian Toyos

license:BSD-3-Clause
This module converts the object layout of a level of Sonic Pocket Adventure between its binary form, as read by
the game's LoadObjects routine, and an editable text form for the decompilation's asset tools. The binary form
starts with the level's size in screens, then a table of per-screen offsets (relative to byte 2), then the
screen lists in the order of those offsets, each holding its slot, its entry count, and the entries themselves.
"""

import struct
import re

_HEX2 = re.compile(r"^[0-9a-fA-F]{1,2}$")
_HEX4 = re.compile(r"^[0-9a-fA-F]{1,4}$")
_HEX8 = re.compile(r"^[0-9a-fA-F]{8}$")
_DEC = re.compile(r"^-?[0-9]+$")


def _clean(lines):
	"""Return the comment-stripped, non-blank lines of a text form as a list of token lists."""
	if not isinstance(lines, list):
		return None
	result = []
	for line in lines:
		if not isinstance(line, str):
			return None
		hash_pos = line.find("#")
		if hash_pos != -1:
			line = line[:hash_pos]
		if line.strip() == "":
			continue
		result.append(line.split())
	return result


def _parse_dec(token, lo, hi):
	"""Return the value of a decimal token, or None if it is not a bare integer in the given range."""
	if not _DEC.match(token):
		return None
	value = int(token)
	if value < lo or value > hi:
		return None
	return value


def objects_to_text(data):
	"""Return the text form of a level's object layout, or None if the data is not a valid layout."""
	if not isinstance(data, (bytes, bytearray)):
		return None
	if len(data) < 2:
		return None
	nx = data[0]
	ny = data[1]
	count = nx * ny
	table_size = 2 * count
	offsets_len = 2 + table_size
	if len(data) < offsets_len:
		return None
	entries = []
	for i in range(count):
		off = struct.unpack_from("<H", data, 2 + 2 * i)[0]
		x = i % nx
		y = i // nx
		entries.append((off, x, y))
	non_zero = [e for e in entries if e[0] != 0]
	if non_zero:
		non_zero.sort(key=lambda e: e[0])
		offs = [e[0] for e in non_zero]
		if len(set(offs)) != len(offs):
			return None
		if offs[0] != table_size:
			return None
		pos = table_size
		for off, x, y in non_zero:
			if off != pos:
				return None
			base = 2 + off
			end = base + 2
			if end > len(data):
				return None
			cnt = data[base + 1]
			end += 10 * cnt
			pos = end - 2
		if pos != len(data) - 2:
			return None
	else:
		if len(data) != offsets_len:
			return None
	lines = ["grid {} {}".format(nx, ny)]
	for off, x, y in non_zero:
		base = 2 + off
		slot = data[base]
		cnt = data[base + 1]
		lines.append("cell {} {} slot {}".format(x, y, slot))
		p = base + 2
		for _ in range(cnt):
			id_b = data[p]
			param = data[p + 1]
			ox = struct.unpack_from("<H", data, p + 2)[0]
			oy = struct.unpack_from("<H", data, p + 4)[0]
			extra = data[p + 6:p + 10].hex().upper()
			lines.append("obj {:02X} {:02X} {:04X} {:04X} {}".format(id_b, param, ox, oy, extra))
			p += 10
	if objects_from_text(lines) != bytes(data):
		return None
	return lines


def objects_from_text(lines):
	"""Return the binary form of a level's object layout, or None if the text is not a valid layout."""
	clean = _clean(lines)
	if clean is None or len(clean) == 0:
		return None
	first = clean[0]
	if len(first) != 3 or first[0] != "grid":
		return None
	nx = _parse_dec(first[1], 0, 255)
	ny = _parse_dec(first[2], 0, 255)
	if nx is None or ny is None:
		return None
	count = nx * ny
	seen = set()
	cells = []
	i = 1
	while i < len(clean):
		tok = clean[i]
		if len(tok) != 5 or tok[0] != "cell" or tok[3] != "slot":
			return None
		x = _parse_dec(tok[1], 0, 255)
		y = _parse_dec(tok[2], 0, 255)
		slot = _parse_dec(tok[4], 0, 255)
		if x is None or y is None or slot is None:
			return None
		if x >= nx or y >= ny:
			return None
		key = (x, y)
		if key in seen:
			return None
		seen.add(key)
		entries = []
		i += 1
		while i < len(clean) and clean[i][0] == "obj":
			otok = clean[i]
			if len(otok) != 6:
				return None
			if not _HEX2.match(otok[1]) or not _HEX2.match(otok[2]):
				return None
			if not _HEX4.match(otok[3]) or not _HEX4.match(otok[4]):
				return None
			if not _HEX8.match(otok[5]):
				return None
			id_b = int(otok[1], 16)
			param = int(otok[2], 16)
			ox = int(otok[3], 16)
			oy = int(otok[4], 16)
			extra = bytes.fromhex(otok[5])
			entries.append((id_b, param, ox, oy, extra))
			if len(entries) > 255:
				return None
			i += 1
		cells.append((x, y, slot, entries))
	offsets = [0] * count
	base = 2 * count
	for x, y, slot, entries in cells:
		idx = y * nx + x
		if offsets[idx] != 0:
			return None
		if base > 0xFFFF:
			return None
		offsets[idx] = base
		base += 2 + 10 * len(entries)
	out = bytearray()
	out.append(nx)
	out.append(ny)
	for off in offsets:
		out += struct.pack("<H", off)
	for x, y, slot, entries in cells:
		out.append(slot)
		out.append(len(entries))
		for id_b, param, ox, oy, extra in entries:
			out.append(id_b)
			out.append(param)
			out += struct.pack("<H", ox)
			out += struct.pack("<H", oy)
			out += extra
	return bytes(out)
