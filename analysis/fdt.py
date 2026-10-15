"""Minimal flattened-device-tree (DTB) reader. Standard library only.

Enough to diff two DTBs property by property and to resolve phandles to node names and labels.
"""
import struct

FDT_MAGIC = 0xD00DFEED
BEGIN_NODE, END_NODE, PROP, NOP, END = 1, 2, 3, 4, 9


def parse(blob):
    """Return {path: {prop: bytes}} for every node, paths like '/soc/pwm@3ad044000'."""
    magic, _total, off_struct, off_strings = struct.unpack(">IIII", blob[:16])
    if magic != FDT_MAGIC:
        raise ValueError("not a DTB")
    nodes, stack, i = {}, [], off_struct
    while True:
        (tok,) = struct.unpack(">I", blob[i:i + 4])
        i += 4
        if tok == BEGIN_NODE:
            end = blob.index(b"\0", i)
            stack.append(blob[i:end].decode())
            i = (end + 4) & ~3
            nodes["/" + "/".join(n for n in stack if n)] = {}
        elif tok == END_NODE:
            stack.pop()
        elif tok == PROP:
            length, name_off = struct.unpack(">II", blob[i:i + 8])
            i += 8
            name = blob[off_strings + name_off:blob.index(b"\0", off_strings + name_off)].decode()
            nodes["/" + "/".join(n for n in stack if n)][name] = blob[i:i + length]
            i = (i + length + 3) & ~3
        elif tok == NOP:
            continue
        elif tok == END:
            return nodes
        else:
            raise ValueError(f"bad token {tok:#x} at {i - 4}")


def phandles(nodes):
    """Return {phandle: (path, label)}."""
    out = {}
    for path, props in nodes.items():
        if "phandle" in props:
            label = props.get("label", b"").rstrip(b"\0").decode(errors="replace")
            out[struct.unpack(">I", props["phandle"])[0]] = (path, label)
    return out


def find_dtb(blob):
    """Offset and size of the first well-formed DTB inside a larger blob (e.g. an m1n1 boot image).

    m1n1's own code also contains the magic constant, so candidates are checked for a sane size.
    """
    i = blob.find(struct.pack(">I", FDT_MAGIC))
    while i != -1:
        (size,) = struct.unpack(">I", blob[i + 4:i + 8])
        if 1000 < size < 2_000_000:
            try:
                parse(blob[i:i + size])
                return i, size
            except (ValueError, struct.error, IndexError):
                pass
        i = blob.find(struct.pack(">I", FDT_MAGIC), i + 4)
    raise ValueError("no DTB found")
