"""
Name:        wav.py
Description: 8-bit unsigned mono PCM (the SEGA voice) as a RIFF WAVE file, and back
Version:     0.1.0
Created:     28-11-2026
Modified:    28-11-2026
Author:      Sebastian Toyos

license:BSD-3-Clause
This module provides two functions for the decompilation asset tools: pcm_to_wav builds a RIFF WAVE file from
raw 8-bit unsigned mono PCM samples and a sample rate, and wav_to_pcm parses such a file back into its raw PCM
bytes. The WAVE format used is the standard RIFF container with a fmt chunk describing 8-bit PCM mono audio and
a data chunk holding the samples, with one zero pad byte appended after the data when its length is odd.
"""

import struct


def pcm_to_wav(data, rate):
	"""Build a RIFF WAVE file from 8-bit unsigned mono PCM data and a sample rate."""
	if not isinstance(data, (bytes, bytearray)):
		return None
	if not isinstance(rate, int) or isinstance(rate, bool) or rate < 0:
		return None

	pad = 1 if len(data) % 2 else 0
	riff_size = 4 + (8 + 16) + (8 + len(data) + pad)

	out = bytearray()
	out += b"RIFF"
	out += struct.pack("<I", riff_size)
	out += b"WAVE"

	# fmt chunk
	out += b"fmt "
	out += struct.pack("<I", 16)
	out += struct.pack("<HHIIHH", 1, 1, rate, rate, 1, 8)

	# data chunk
	out += b"data"
	out += struct.pack("<I", len(data))
	out += bytes(data)
	if pad:
		out += b"\x00"

	return bytes(out)


def wav_to_pcm(wav):
	"""Parse a RIFF WAVE file and return its 8-bit mono PCM data, or None if the file is not a valid 8-bit mono PCM WAVE."""
	if not isinstance(wav, (bytes, bytearray)):
		return None

	if len(wav) < 12:
		return None

	if wav[0:4] != b"RIFF":
		return None
	if wav[8:12] != b"WAVE":
		return None

	try:
		riff_size = struct.unpack_from("<I", wav, 4)[0]
	except struct.error:
		return None

	end = 12 + riff_size
	if end > len(wav):
		end = len(wav)

	pos = 12
	fmt_found = False
	fmt_ok = False
	data_found = False
	pcm_data = None

	while pos < end:
		if pos + 8 > end:
			return None

		chunk_id = wav[pos:pos+4]
		try:
			chunk_size = struct.unpack_from("<I", wav, pos+4)[0]
		except struct.error:
			return None

		pos += 8

		if pos + chunk_size > end:
			return None

		chunk_data = wav[pos:pos+chunk_size]
		pos += chunk_size

		# Skip the pad byte if the chunk size is odd and there is room for it
		if chunk_size % 2:
			if pos < end:
				pos += 1

		if chunk_id == b"fmt ":
			if fmt_found:
				return None
			fmt_found = True
			if len(chunk_data) < 16:
				return None
			try:
				audio_format, num_channels, sample_rate, byte_rate, block_align, bits_per_sample = struct.unpack_from("<HHIIHH", chunk_data, 0)
			except struct.error:
				return None
			if audio_format != 1:
				return None
			if num_channels != 1:
				return None
			if bits_per_sample != 8:
				return None
			fmt_ok = True

		elif chunk_id == b"data":
			if not fmt_found or not fmt_ok:
				return None
			if data_found:
				return None
			data_found = True
			pcm_data = chunk_data
			break

	if not data_found or pcm_data is None:
		return None

	return bytes(pcm_data)
