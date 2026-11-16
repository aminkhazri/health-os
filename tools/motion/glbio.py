import json, struct, numpy as np
CT = {5120:'b',5121:'B',5122:'h',5123:'H',5125:'I',5126:'f'}; NC = {'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}
def load(path):
    b = open(path,'rb').read(); n = struct.unpack('<I', b[12:16])[0]; j = json.loads(b[20:20+n]); o = 20+n
    m = struct.unpack('<I', b[o:o+4])[0]; return j, bytearray(b[o+8:o+8+m])
def acc(j, bin_, i):
    a = j['accessors'][i]; v = j['bufferViews'][a['bufferView']]; t = np.dtype(CT[a['componentType']]); k = NC[a['type']]
    off = v.get('byteOffset',0)+a.get('byteOffset',0); stride = v.get('byteStride') or t.itemsize*k
    raw = np.frombuffer(bytes(bin_), dtype=np.uint8, count=stride*(a['count']-1)+t.itemsize*k, offset=off)
    if stride == t.itemsize*k: return raw.view(t).reshape(a['count'], k).astype(float)
    return np.stack([raw[r*stride:r*stride+t.itemsize*k].view(t) for r in range(a['count'])]).astype(float)
def save(path, j, bin_):
    while len(bin_) % 4: bin_ += b'\0'
    j['buffers'][0]['byteLength'] = len(bin_); js = json.dumps(j, separators=(',',':')).encode()
    while len(js) % 4: js += b' '
    out = struct.pack('<III', 0x46546C67, 2, 12+8+len(js)+8+len(bin_)) + struct.pack('<II', len(js), 0x4E4F534A) + js + struct.pack('<II', len(bin_), 0x004E4942) + bytes(bin_)
    open(path,'wb').write(out)
