"""Turn the free Mesh2Motion mannequin into the Health OS model file.

The mannequin (CC0, mesh2motion.org) is a professionally built and rigged figure: an artist's drawing mannequin with separate
segments at every joint, so it keeps its shape however far a joint bends. Its download bundles 75 animations and a texture;
the app needs only the figure and the push-up. This script:

  1. keeps the mesh, the skeleton and the skin, and drops the texture and every animation except the ones asked for;
  2. renames the bones to the names the app's viewer uses (pelvis -> Hips, upperarm_l -> LeftArm, ...);
  3. scales everything to 1.70 m, the height the app's scene is laid out for;
  4. writes a compact .glb.

Usage: python3 mannequin.py <human-addon-animations.glb> <out.glb> [SourceClip=AppName ...]
"""
import sys, json, numpy as np
import glbio

HEIGHT = 1.70
NAMES = {'pelvis': 'Hips', 'spine_01': 'Spine', 'spine_02': 'Spine1', 'spine_03': 'Spine2', 'neck_01': 'Neck', 'head': 'Head', 'head_leaf': 'HeadTop_End'}
for S, s in (('Left', 'l'), ('Right', 'r')):
    NAMES.update({'clavicle_' + s: S + 'Shoulder', 'upperarm_' + s: S + 'Arm', 'lowerarm_' + s: S + 'ForeArm', 'hand_' + s: S + 'Hand', 'thigh_' + s: S + 'UpLeg',
                  'calf_' + s: S + 'Leg', 'foot_' + s: S + 'Foot', 'ball_' + s: S + 'ToeBase', 'ball_leaf_' + s: S + 'Toe_End'})
    for f in ('thumb', 'index', 'middle', 'ring', 'pinky'):
        for k in (1, 2, 3): NAMES['%s_0%d_%s' % (f, k, s)] = '%sHand%s%d' % (S, f.capitalize(), k)
        NAMES['%s_04_leaf_%s' % (f, s)] = '%sHand%s4' % (S, f.capitalize())
DT = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}; NC = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}

def raw(j, b, i):
    a = j['accessors'][i]; v = j['bufferViews'][a['bufferView']]; t = np.dtype(DT[a['componentType']]); k = NC[a['type']]
    off = v.get('byteOffset', 0) + a.get('byteOffset', 0); stride = v.get('byteStride') or t.itemsize * k
    buf = np.frombuffer(bytes(b), np.uint8, stride * (a['count'] - 1) + t.itemsize * k, off)
    rows = buf.view(t).reshape(a['count'], k) if stride == t.itemsize * k else np.stack([buf[r * stride:r * stride + t.itemsize * k].view(t) for r in range(a['count'])])
    return rows.copy(), a

def main(src, out, pairs):
    j, b = glbio.load(src); N = j['nodes']
    top = float(max(raw(j, b, j['meshes'][0]['primitives'][0]['attributes']['POSITION'])[0][:, 1])); k = HEIGHT / top
    nj = {'asset': {'version': '2.0', 'generator': 'health-os tools/motion/mannequin.py'}, 'scene': 0, 'scenes': j['scenes'], 'buffers': [{}], 'bufferViews': [], 'accessors': [], 'animations': []}
    nb = bytearray()
    def put(arr, src_acc, target=None, minmax=False):
        while len(nb) % 4: nb.append(0)
        v = {'buffer': 0, 'byteOffset': len(nb), 'byteLength': arr.nbytes}
        if target: v['target'] = target
        nb.extend(arr.tobytes()); nj['bufferViews'].append(v)
        a = {'bufferView': len(nj['bufferViews']) - 1, 'componentType': src_acc['componentType'], 'count': len(arr), 'type': src_acc['type']}
        if src_acc.get('normalized'): a['normalized'] = True
        if minmax: a['min'] = [float(x) for x in arr.min(axis=0)]; a['max'] = [float(x) for x in arr.max(axis=0)]
        nj['accessors'].append(a); return len(nj['accessors']) - 1
    # nodes: renamed, bone offsets scaled
    nj['nodes'] = []
    for n in N:
        m = dict(n); m['name'] = NAMES.get(n.get('name'), n.get('name'))
        if 'translation' in m: m['translation'] = [x * k for x in m['translation']]
        nj['nodes'].append(m)
    # mesh: positions scaled; no texture coordinates, the app paints the figure itself
    p = j['meshes'][0]['primitives'][0]; at = p['attributes']; prim = {'attributes': {}, 'mode': 4, 'material': 0}
    for name in ('POSITION', 'NORMAL', 'JOINTS_0', 'WEIGHTS_0'):
        arr, a = raw(j, b, at[name])
        if name == 'POSITION': arr = (arr * k).astype(np.float32)
        prim['attributes'][name] = put(arr, a, 34962, name == 'POSITION')
    arr, a = raw(j, b, p['indices']); prim['indices'] = put(arr, a, 34963)
    nj['meshes'] = [{'name': 'Mannequin', 'primitives': [prim]}]
    nj['materials'] = [{'name': 'Mannequin', 'pbrMetallicRoughness': {'baseColorFactor': [0.86, 0.87, 0.9, 1], 'metallicFactor': 0, 'roughnessFactor': 0.6}}]
    ibm, a = raw(j, b, j['skins'][0]['inverseBindMatrices']); ibm[:, 12:15] *= k
    nj['skins'] = [{'name': 'Armature', 'joints': j['skins'][0]['joints'], 'inverseBindMatrices': put(ibm.astype(np.float32), a)}]
    if 'skeleton' in j['skins'][0]: nj['skins'][0]['skeleton'] = j['skins'][0]['skeleton']
    # the clips asked for, under the names the app uses
    for pair in pairs:
        src_name, app_name = pair.split('=')
        an = next(x for x in j['animations'] if x['name'] == src_name); samplers, channels, seen = [], [], {}
        for c in an['channels']:
            if c['target']['path'] == 'scale': continue
            s = an['samplers'][c['sampler']]
            if s['input'] not in seen: t, ta = raw(j, b, s['input']); seen[s['input']] = put(t, ta, None, True)
            o, oa = raw(j, b, s['output'])
            if c['target']['path'] == 'translation': o = (o * k).astype(np.float32)
            samplers.append({'input': seen[s['input']], 'output': put(o, oa), 'interpolation': s.get('interpolation', 'LINEAR')})
            channels.append({'sampler': len(samplers) - 1, 'target': c['target']})
        nj['animations'].append({'name': app_name, 'samplers': samplers, 'channels': channels})
    glbio.save(out, nj, nb); print('wrote', out, len(nb) // 1024, 'KB', 'scale', round(float(k), 3), 'clips', [a['name'] for a in nj['animations']])

if __name__ == '__main__': main(sys.argv[1], sys.argv[2], sys.argv[3:])
