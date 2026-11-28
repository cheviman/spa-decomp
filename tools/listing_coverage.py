"""
Name:        listing_coverage.py
Description: the share of the cartridge's instructions the scenarios run, against the assembled disassembly's
             listing (build/asm/Main.lst), and the stretches of instructions none of them runs
Version:     0.1.0
Created:     27-11-2026
Modified:    27-11-2026
Author:      Sebastian Toyos

license:BSD-3-Clause
The listing is AS's, of Valley Bell's disassembly assembled with its asw (its labels are the original's
addresses: docs/plan.md, the first round), so it says where every instruction of the cartridge starts until the
TLCS-900H decoder does (step 5). The traces are ngpref --trace's, the addresses executed. It writes on stdout how
many of the instructions each trace ran and all of them together, and the addresses run that are not an
instruction's start (none when the listing and the cartridge agree); --never the stretches of instructions no
trace ran, under their label; --labels each label's instructions run and in all.
  py tools/listing_coverage.py [--listing FILE] [--never FILE] [--labels FILE] TRACE [TRACE ...]
"""
import argparse
import re

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


class Instruction:
	"""An instruction of the listing: where it starts, its length, and the label it is under."""
	def __init__(self, address, length, label, label_address):
		self.address = address
		self.length = length
		self.label = label
		self.label_address = label_address


def parse_listing(path):
	"""The listing's instructions in 200000-3FFFFF, in its order, and its other lines with bytes (the statement
	words of the lines that are neither an instruction nor db, dw or dd: macros that write data, as a count and
	the distinct words)."""
	instructions = []
	other_count = 0
	other_words = set()
	label, label_address = "?", None
	numbered = []          # the addresses of the numbered lines, in order
	ins3 = []              # (instruction, its index in numbered): INS3's length is up to the next address
	extendable = None      # the instruction the continuation lines that follow add bytes to
	with open(path, encoding="latin-1") as listing:
		for line in listing:
			line = line.rstrip("\r\n")
			match = NUMBERED.match(line)
			if not match:
				more = CONTINUATION.match(line)
				if more and extendable:
					extendable.length += len(more.group(1)) // 3
				continue
			extendable = None
			address = int(match.group(1), 16)
			field, source = match.group(2)[:20], match.group(2)[20:]
			named = LABEL.match(source)
			if named:
				label, label_address = named.group(1), address
				source = source[named.end():]
			words = source.split(";")[0].split()
			word = words[0].lower() if words else ""
			numbered.append(address)
			if address not in CARTRIDGE:
				continue
			has_bytes = BYTES.match(field) is not None
			if has_bytes and word in MNEMONICS:
				extendable = Instruction(address, len(field.split()), label, label_address)
				instructions.append(extendable)
			elif field.startswith("(MACRO)") and word == "ins3":
				instructions.append(Instruction(address, 0, label, label_address))
				ins3.append((instructions[-1], len(numbered) - 1))
			elif has_bytes and word not in DATA_WORDS:
				other_count += 1
				other_words.add(word)
	for instruction, index in ins3:
		following = next((a for a in numbered[index + 1:] if a != instruction.address), instruction.address)
		instruction.length = following - instruction.address
	# The instructions before any label are under '?', at the first of them
	for instruction in instructions:
		if instruction.label_address is None:
			instruction.label_address = instructions[0].address
	return instructions, other_count, sorted(other_words)


def read_trace(path):
	"""The addresses in 200000-3FFFFF an ngpref --trace file holds."""
	with open(path, encoding="latin-1") as trace:
		return {int(line, 16) for line in (text.strip() for text in trace) if line and not line.startswith("#")
			and int(line, 16) in CARTRIDGE}


def listed(items):
	"""The first ten of a list, space-separated, and ' ...' when there are more."""
	return " ".join(items[:10]) + (" ..." if len(items) > 10 else "")


def trace_line(name, addresses, index, instructions, total_bytes):
	"""A trace's line of the summary, and the indexes of the instructions it ran."""
	ran = {index[address] for address in addresses if address in index}
	not_starts = sorted(address for address in addresses if address not in index)
	line = (f"{name}: {len(ran)} of {len(instructions)} instructions run ({100 * len(ran) / len(instructions):.2f}%), "
		f"{sum(instructions[i].length for i in ran)} of {total_bytes} bytes; not instruction starts: {len(not_starts)}")
	if not_starts:
		line += f" ({listed(['%06X' % address for address in not_starts])})"
	return line, ran


def stretches_never_run(instructions, ran):
	"""The stretches of consecutive instructions none ran, each under one label, as (first, last) indexes."""
	stretches = []
	for i, instruction in enumerate(instructions):
		if i in ran:
			continue
		if stretches and stretches[-1][1] == i - 1 and instructions[i - 1].label == instruction.label:
			stretches[-1] = (stretches[-1][0], i)
		else:
			stretches.append((i, i))
	return stretches


def main():
	parser = argparse.ArgumentParser(description="The share of the cartridge's instructions ngpref's traces run.")
	parser.add_argument("--listing", default="build/asm/Main.lst", help="AS's listing of the disassembly")
	parser.add_argument("--never", help="the stretches of instructions no trace ran")
	parser.add_argument("--labels", help="each label's instructions, run and in all")
	parser.add_argument("traces", nargs="+", help="ngpref --trace files")
	args = parser.parse_args()

	instructions, other_count, other_words = parse_listing(args.listing)
	index = {instruction.address: i for i, instruction in enumerate(instructions)}
	total_bytes = sum(instruction.length for instruction in instructions)
	line = f"listing: {len(instructions)} instructions, {total_bytes} bytes, at 200000-3FFFFF; other lines with bytes: {other_count}"
	print(line + (f" ({listed(other_words)})" if other_count else ""))
	every = set()
	for name in args.traces:
		addresses = read_trace(name)
		every |= addresses
		print(trace_line(name, addresses, index, instructions, total_bytes)[0])
	line, ran = trace_line("all", every, index, instructions, total_bytes)
	print(line)
	stretches = stretches_never_run(instructions, ran)
	print(f"never run: {len(stretches)} stretches, {sum(last - first + 1 for first, last in stretches)} instructions")

	if args.never:
		with open(args.never, "w", encoding="latin-1", newline="\n") as out:
			out.write("# instructions no trace ran, a stretch a line (consecutive, under one label): first, last, "
				"instructions, where\n")
			for first, last in stretches:
				start = instructions[first]
				offset = start.address - start.label_address
				where = start.label + (f"+{offset:X}" if offset else "")
				out.write(f"{start.address:06X} {instructions[last].address:06X} {last - first + 1} {where}\n")
	if args.labels:
		labels = {}
		for i, instruction in enumerate(instructions):
			counts = labels.setdefault((instruction.label_address, instruction.label), [0, 0])
			counts[0] += i in ran
			counts[1] += 1
		with open(args.labels, "w", encoding="latin-1", newline="\n") as out:
			out.write("# labels with instructions: address, name, instructions run, instructions\n")
			for (address, name), (run, total) in labels.items():
				out.write(f"{address:06X} {name} {run} {total}\n")


if __name__ == "__main__":
	main()
