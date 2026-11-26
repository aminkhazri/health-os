"""Minimal reader for Blender .blend files (64-bit little-endian, uncompressed): enough to pull objects and meshes out without Blender."""
import struct, re, mmap
import numpy as np


class Blend:
    def __init__(self, path):
        self.f = open(path, 'rb'); self.m = mmap.mmap(self.f.fileno(), 0, access=mmap.ACCESS_READ)
        assert self.m[:7] == b'BLENDER' and self.m[7:9] == b'-v', 'needs a 64-bit little-endian file'
        self.version = int(self.m[9:12]); self.blocks = {}; self.by_code = {}; self.owned = {}; cur = None
        o = 12
        while True:
            code, size, old, sdna, count = struct.unpack_from('<4sIQII', self.m, o); o += 24
            code = code.rstrip(b'\0').decode()
            if code == 'DNA1': self._dna(o)
            if code == 'ENDB': break
            # Addresses can repeat across the file, so data blocks are also filed under the datablock they follow (their owner).
            if code == 'DATA':
                if cur is not None: self.owned[cur].setdefault(old, (o, size, sdna, count, code))
                self.blocks.setdefault(old, (o, size, sdna, count, code))
            else:
                cur = old; self.owned[cur] = {}; self.blocks[old] = (o, size, sdna, count, code); self.by_code.setdefault(code, []).append(old)
            o += size

    def _dna(self, o):
        m = self.m; base = o; al = lambda x: base + ((x - base + 3) & ~3); assert m[o:o + 8] == b'SDNANAME'; n = struct.unpack_from('<I', m, o + 8)[0]; o += 12
        def strings(o, n):
            out = []
            for _ in range(n):
                e = m.find(b'\0', o); out.append(m[o:e].decode()); o = e + 1
            return out, al(o)
        names, o = strings(o, n); assert m[o:o + 4] == b'TYPE'; n = struct.unpack_from('<I', m, o + 4)[0]
        types, o = strings(o + 8, n); assert m[o:o + 4] == b'TLEN'; o += 4
        tlen = struct.unpack_from('<%dH' % len(types), m, o); o = al(o + 2 * len(types))
        assert m[o:o + 4] == b'STRC'; n = struct.unpack_from('<I', m, o + 4)[0]; o += 8
        self.structs = []; self.struct_by_name = {}; self.tlen = dict(zip(types, tlen))
        for _ in range(n):
            t, nf = struct.unpack_from('<HH', m, o); o += 4; fields = {}; off = 0
            for _ in range(nf):
                ft, fn = struct.unpack_from('<HH', m, o); o += 4; name = names[fn]; ftype = types[ft]
                ptr = name.startswith('*') or name.startswith('(*'); dims = [int(x) for x in re.findall(r'\[(\d+)\]', name)]
                cnt = int(np.prod(dims)) if dims else 1; size = (8 if ptr else tlen[ft]) * cnt
                key = re.sub(r'\[.*', '', name).lstrip('*').replace('(*', '').replace(')()', '').rstrip(')')
                fields[key] = (off, ftype, ptr, cnt, size); off += size
            self.structs.append((types[t], fields)); self.struct_by_name[types[t]] = fields

    def struct_of(self, ptr): return self.structs[self.blocks[ptr][2]]

    def read(self, base, fields, name, fmt=None):
        """Value of one field of a struct that starts at file offset `base`. Nested names use dots: 'vdata.totlayer'."""
        for part in name.split('.')[:-1]:
            off, ftype, ptr, cnt, size = fields[part]; base += off; fields = self.struct_by_name[ftype]
        off, ftype, ptr, cnt, size = fields[name.split('.')[-1]]; o = base + off
        if ptr: return struct.unpack_from('<Q', self.m, o)[0] if cnt == 1 else struct.unpack_from('<%dQ' % cnt, self.m, o)
        if ftype == 'char': return self.m[o:o + cnt].split(b'\0')[0].decode('utf8', 'replace') if cnt > 1 else self.m[o]
        code = {'int': 'i', 'float': 'f', 'short': 'h', 'double': 'd', 'uchar': 'B', 'int8_t': 'b', 'uint64_t': 'Q', 'int64_t': 'q', 'ushort': 'H', 'uint': 'I'}.get(ftype)
        if code is None: return (o, ftype)          # embedded struct: give back where it is
        v = struct.unpack_from('<%d%s' % (cnt, code), self.m, o); return v[0] if cnt == 1 else v

    def at(self, ptr): o, size, sdna, count, code = self.blocks[ptr]; return o, self.structs[sdna][1]

    def array(self, ptr, dtype, n, shape=None, owner=None):
        blk = self.owned.get(owner, {}).get(ptr) or self.blocks[ptr]; o = blk[0]; assert blk[1] >= n * np.dtype(dtype).itemsize, 'block too small'
        a = np.frombuffer(self.m, dtype, n, o); return a.reshape(shape) if shape else a
