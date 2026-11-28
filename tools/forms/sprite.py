"""
Name:        sprite.py
Description: a sprite of the cartridge (a .spr file, read by CopySprites) as text, and its picture
Version:     0.1.0
Created:     28-11-2026
Modified:    28-11-2026
Author:      Sebastian Toyos

license:BSD-3-Clause
This module provides a pair of functions to convert a sprite entry block, as read by the game's CopySprites
routine, into a list of text lines and back, and a function to render the sprite into a list of pixel values.
The binary format starts with a little-endian u16 tile count, followed by a sequence of four-byte single-tile
entries or eight-byte column entries, with any trailing partial bytes preserved verbatim.
"""

import struct
import re


def _parse_decimal(token):
	"""Parse a decimal integer token consisting of an optional minus sign and digits."""
	if not token:
		return None
	if token[0] == '-':
		if len(token) == 1:
			return None
		body = token[1:]
		if not body.isdigit():
			return None
		return -int(body)
	if not token.isdigit():
		return None
	return int(token)


def _parse_hex(token, min_digits, max_digits, max_value=None):
	"""Parse a hexadecimal token with a constrained digit count and optional maximum value."""
	if len(token) < min_digits or len(token) > max_digits:
		return None
	if not re.fullmatch(r'[0-9A-Fa-f]+', token):
		return None
	value = int(token, 16)
	if max_value is not None and value > max_value:
		return None
	return value


def _signed_byte(value):
	"""Encode a signed integer in the range -128 to 127 as a single byte."""
	return value & 0xFF


def _clean_lines(lines):
	"""Remove comments and blank lines from a list of text lines, returning None on invalid input."""
	if not isinstance(lines, (list, tuple)):
		return None
	cleaned = []
	for line in lines:
		if not isinstance(line, str):
			return None
		hash_pos = line.find('#')
		if hash_pos != -1:
			line = line[:hash_pos]
		line = line.strip()
		if not line:
			continue
		cleaned.append(line)
	return cleaned


def _build_bytes(cleaned):
	"""Build the binary sprite data from a list of cleaned text lines, returning None on invalid input."""
	if not cleaned:
		return None
	first_tokens = cleaned[0].split()
	if len(first_tokens) != 2 or first_tokens[0] != 'tiles':
		return None
	n = _parse_decimal(first_tokens[1])
	if n is None or n < 0 or n > 65535:
		return None
	out = bytearray()
	out += struct.pack('<H', n)
	for line in cleaned[1:]:
		tokens = line.split()
		if not tokens:
			continue
		kind = tokens[0]
		if kind == 'tile':
			if len(tokens) != 4:
				return None
			t = _parse_hex(tokens[1], 1, 4, max_value=0xFFFF)
			if t is None or t == 0xFFFF:
				return None
			x = _parse_decimal(tokens[2])
			if x is None or x < -128 or x > 127:
				return None
			y = _parse_decimal(tokens[3])
			if y is None or y < -128 or y > 127:
				return None
			out += struct.pack('<H', t)
			out += bytes([_signed_byte(x), _signed_byte(y)])
		elif kind == 'column':
			if len(tokens) != 5:
				return None
			t = _parse_hex(tokens[1], 1, 4, max_value=0xFFFF)
			if t is None:
				return None
			x = _parse_decimal(tokens[2])
			if x is None or x < -128 or x > 127:
				return None
			y = _parse_decimal(tokens[3])
			if y is None or y < -128 or y > 127:
				return None
			c = _parse_decimal(tokens[4])
			if c is None or c < 0 or c > 65535:
				return None
			out += struct.pack('<H', 0xFFFF)
			out += struct.pack('<H', c)
			out += struct.pack('<H', t)
			out += bytes([_signed_byte(x), _signed_byte(y)])
		elif kind == 'bytes':
			if len(tokens) < 2:
				return None
			for tok in tokens[1:]:
				b = _parse_hex(tok, 1, 2, max_value=0xFF)
				if b is None:
					return None
				out += bytes([b])
		else:
			return None
	return bytes(out)


def _to_text(data):
	"""Convert the binary sprite data into a list of text lines without verification, returning None if too short."""
	if not isinstance(data, (bytes, bytearray)):
		return None
	data = bytes(data)
	if len(data) < 2:
		return None
	n = struct.unpack_from('<H', data, 0)[0]
	lines = ['tiles ' + str(n)]
	p = 2
	while p < len(data):
		remaining = len(data) - p
		if remaining < 4:
			chunk = data[p:]
			tokens = []
			for byte in chunk:
				tokens.append(format(byte, '02X'))
			lines.append('bytes ' + ' '.join(tokens))
			break
		w = struct.unpack_from('<H', data, p)[0]
		if w == 0xFFFF:
			if remaining < 8:
				chunk = data[p:]
				tokens = []
				for byte in chunk:
					tokens.append(format(byte, '02X'))
				lines.append('bytes ' + ' '.join(tokens))
				break
			c = struct.unpack_from('<H', data, p + 2)[0]
			t = struct.unpack_from('<H', data, p + 4)[0]
			x = struct.unpack_from('<b', data, p + 6)[0]
			y = struct.unpack_from('<b', data, p + 7)[0]
			lines.append('column ' + format(t, '04X') + ' ' + str(x) + ' ' + str(y) + ' ' + str(c))
			p += 8
		else:
			x = struct.unpack_from('<b', data, p + 2)[0]
			y = struct.unpack_from('<b', data, p + 3)[0]
			lines.append('tile ' + format(w, '04X') + ' ' + str(x) + ' ' + str(y))
			p += 4
	return lines


def sprite_to_text(data):
	"""Convert the binary sprite data into a list of text lines, returning None if the data is too short or invalid."""
	lines = _to_text(data)
	if lines is None:
		return None
	result = _build_bytes(lines)
	if result != data:
		return None
	return lines


def sprite_from_text(lines):
	"""Convert a list of text lines into binary sprite data, returning None if the input is invalid."""
	cleaned = _clean_lines(lines)
	if cleaned is None:
		return None
	result = _build_bytes(cleaned)
	if result is None:
		return None
	return result


def sprite_picture(data, tiles):
	"""Render the sprite into a list of pixel rows, returning a tuple of (rows, left, top) or None."""
	if not isinstance(data, (bytes, bytearray)) or not isinstance(tiles, (bytes, bytearray)):
		return None
	data = bytes(data)
	tiles = bytes(tiles)
	if len(data) < 2:
		return None
	p = 2
	pieces = []
	while p < len(data):
		remaining = len(data) - p
		if remaining < 4:
			break
		w = struct.unpack_from('<H', data, p)[0]
		if w == 0xFFFF:
			if remaining < 8:
				break
			c = struct.unpack_from('<H', data, p + 2)[0]
			t = struct.unpack_from('<H', data, p + 4)[0]
			x = struct.unpack_from('<b', data, p + 6)[0]
			y = struct.unpack_from('<b', data, p + 7)[0]
			count = c & 0xFF
			for k in range(count):
				pieces.append((t + k, x, y + 8 * k))
			p += 8
		else:
			x = struct.unpack_from('<b', data, p + 2)[0]
			y = struct.unpack_from('<b', data, p + 3)[0]
			pieces.append((w, x, y))
			p += 4
	if not pieces:
		return None
	valid_pieces = []
	for piece in pieces:
		tile_id = piece[0]
		if 16 * tile_id + 16 > len(tiles):
			continue
		valid_pieces.append(piece)
	if not valid_pieces:
		return None
	left = min(piece[1] for piece in valid_pieces)
	top = min(piece[2] for piece in valid_pieces)
	width = max(piece[1] + 8 for piece in valid_pieces) - left
	height = max(piece[2] + 8 for piece in valid_pieces) - top
	rows = []
	for r in range(height):
		row = [0] * width
		rows.append(row)
	for piece in reversed(valid_pieces):
		tile_id, x, y = piece
		tile_base = 16 * tile_id
		for r in range(8):
			word = struct.unpack_from('<H', tiles, tile_base + 2 * r)[0]
			for px in range(8):
				pixel = (word >> (14 - 2 * px)) & 3
				if pixel != 0:
					gx = x + px - left
					gy = y + r - top
					if 0 <= gx < width and 0 <= gy < height:
						rows[gy][gx] = pixel
	return (rows, left, top)
