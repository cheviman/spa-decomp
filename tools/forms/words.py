"""
Name:        words.py
Description: a binary file of little-endian 16-bit words as lines of hex words, and back
Version:     0.1.0
Created:     28-11-2026
Modified:    28-11-2026
Author:      Sebastian Toyos

license:BSD-3-Clause
This module converts a binary blob of little-endian 16-bit words (such as a level's block layout, block tile
maps, tile collision values, palette lists, or palette lines) into a text form of hex words and back, for the
asset tools of a decompilation. The text form starts with a header line that gives the word count and the
layout width, followed by the words as four-digit hex tokens, W per line, with an optional line index in a
comment.
"""

import re

_HEX_TOKEN_RE = re.compile(r"^[0-9a-fA-F]{1,4}$")
_DEC_TOKEN_RE = re.compile(r"^-?[0-9]+$")


def _strip_comment(line):
	"""Remove the comment part of a line, from the first '#' to the end, and strip whitespace."""
	if not isinstance(line, str):
		return ""
	pos = line.find("#")
	if pos >= 0:
		line = line[:pos]
	return line.strip()


def _parse_decimal(token):
	"""Parse a decimal token (optional '-' and digits) into an int, or None if it is not one."""
	if not isinstance(token, str):
		return None
	if not _DEC_TOKEN_RE.match(token):
		return None
	return int(token)


def _parse_hex(token):
	"""Parse a hex token of 1 to 4 digits into an int, or None if it is not one."""
	if not isinstance(token, str):
		return None
	if not _HEX_TOKEN_RE.match(token):
		return None
	return int(token, 16)


def words_to_text(data, width, index=False):
	"""Convert a bytes object of little-endian 16-bit words to a list of text lines, or None if it cannot."""
	if not isinstance(data, (bytes, bytearray)):
		return None
	if not isinstance(width, int) or isinstance(width, bool):
		return None
	if width < 1:
		return None
	if len(data) % 2 != 0:
		return None

	n = len(data) // 2
	lines = ["words {} width {}".format(n, width)]

	if n > 0:
		for i in range(0, n, width):
			chunk = data[i * 2:(i + width) * 2]
			tokens = []
			for j in range(0, len(chunk), 2):
				value = chunk[j] | (chunk[j + 1] << 8)
				tokens.append("{:04X}".format(value))
			line = " ".join(tokens)
			if index:
				line += "  # {:04X}".format(i // width)
			lines.append(line)

	check = words_from_text(lines)
	if check is None or bytes(check) != bytes(data):
		return None
	return lines


def words_from_text(lines):
	"""Convert a list of text lines to a bytes object of little-endian 16-bit words, or None if it cannot."""
	if not isinstance(lines, (list, tuple)):
		return None

	cleaned = []
	for line in lines:
		text = _strip_comment(line)
		if text:
			cleaned.append(text)

	if len(cleaned) < 1:
		return None

	header_tokens = cleaned[0].split()
	if len(header_tokens) != 4:
		return None
	if header_tokens[0] != "words":
		return None
	n = _parse_decimal(header_tokens[1])
	if n is None or n < 0:
		return None
	if header_tokens[2] != "width":
		return None
	w = _parse_decimal(header_tokens[3])
	if w is None or w < 1:
		return None

	values = []
	for text in cleaned[1:]:
		for token in text.split():
			value = _parse_hex(token)
			if value is None:
				return None
			values.append(value)

	if len(values) != n:
		return None

	out = bytearray()
	for value in values:
		out.append(value & 0xFF)
		out.append((value >> 8) & 0xFF)
	return bytes(out)
