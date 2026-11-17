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

def add_clip(j, bin_, node_of, times, rot, hips_pos, name):
    """Store an animation in the model: one rotation track per bone (rot[bone] = frames x 4, xyzw) plus the hips' path."""
    def add(arr, typ, minmax=False):
        arr = np.asarray(arr, np.float32); off = len(bin_); bin_.extend(arr.tobytes())
        j['bufferViews'].append({'buffer': 0, 'byteOffset': off, 'byteLength': arr.nbytes})
        a = {'bufferView': len(j['bufferViews']) - 1, 'componentType': 5126, 'count': len(arr), 'type': typ}
        if minmax: a['min'] = [float(arr.min())]; a['max'] = [float(arr.max())]
        j['accessors'].append(a); return len(j['accessors']) - 1
    while len(bin_) % 4: bin_ += b'\0'
    t_in = add(times, 'SCALAR', True); samplers, channels = [], []
    for b, node in node_of.items():
        q = np.array(rot[b], float)
        for f in range(1, len(q)):          # keep neighbouring frames on the same side, so blending never takes the long way round
            if q[f] @ q[f - 1] < 0: q[f] = -q[f]
        samplers.append({'input': t_in, 'output': add(q, 'VEC4'), 'interpolation': 'LINEAR'})
        channels.append({'sampler': len(samplers) - 1, 'target': {'node': node, 'path': 'rotation'}})
    samplers.append({'input': t_in, 'output': add(hips_pos, 'VEC3'), 'interpolation': 'LINEAR'})
    channels.append({'sampler': len(samplers) - 1, 'target': {'node': node_of['Hips'], 'path': 'translation'}})
    j['animations'] = [a for a in j.get('animations', []) if a['name'] != name] + [{'name': name, 'samplers': samplers, 'channels': channels}]

def add_effort(j, bin_, clip, times, effort):
    """Give a clip an effort curve (0 = relaxed, 1 = working hardest). glTF has no slot for a bare number, so it rides on a helper node
    called "Effort": the node's x position is the effort. The app reads it each frame to colour and swell the working muscles."""
    idx = next((i for i, n in enumerate(j['nodes']) if n.get('name') == 'Effort'), None)
    if idx is None:
        j['nodes'].append({'name': 'Effort'}); idx = len(j['nodes']) - 1
        root = j['scenes'][j.get('scene', 0)]['nodes'][0]; j['nodes'][root].setdefault('children', []).append(idx)
    def add(arr, typ, minmax=False):
        arr = np.asarray(arr, np.float32)
        while len(bin_) % 4: bin_.append(0)
        off = len(bin_); bin_.extend(arr.tobytes()); j['bufferViews'].append({'buffer': 0, 'byteOffset': off, 'byteLength': arr.nbytes})
        a = {'bufferView': len(j['bufferViews']) - 1, 'componentType': 5126, 'count': len(arr), 'type': typ}
        if minmax: a['min'] = [float(arr.min())]; a['max'] = [float(arr.max())]
        j['accessors'].append(a); return len(j['accessors']) - 1
    an = next(a for a in j['animations'] if a['name'] == clip)
    an['samplers'].append({'input': add(times, 'SCALAR', True), 'output': add(np.c_[effort, np.zeros(len(effort)), np.zeros(len(effort))], 'VEC3'), 'interpolation': 'LINEAR'})
    an['channels'].append({'sampler': len(an['samplers']) - 1, 'target': {'node': idx, 'path': 'translation'}})
