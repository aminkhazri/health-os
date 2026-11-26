"""Build the Body tab's anatomical model (models/body.glb) from BodyParts3D.

Source: BodyParts3D 4.0, (c) The Database Center for Life Science, licensed CC BY 4.0, in the packed form published by the
open-source "human-atlas" viewer (github.com/ashemag/human-atlas, public/models). Usage:

    python3 tools/anatomy/build_body.py /path/to/human-atlas/public/models models/body.glb [preview.png]

What it does:
  1. picks the skeleton and the muscles that matter for training, and sorts every muscle into one of the app's muscle keys by its name
  2. simplifies each part (vertex clustering) so the whole body is a few megabytes
  3. adds a "fibre" number per point (position across the muscle's long axis) that the app turns into fine fibre lines
  4. BodyParts3D has no latissimus dorsi or rectus abdominis, so those two are generated from the skin surface over the right region
     (an approximation: the outline is drawn from landmarks, not sculpted)
  5. writes one mesh per muscle key, plus 'bone', 'tendon' and 'deep' (muscles shown but not tracked)
"""
import json, re, struct, sys
import numpy as np

SRC, OUT = sys.argv[1], sys.argv[2]
PREVIEW = sys.argv[3] if len(sys.argv) > 3 else None
atlas = json.load(open(SRC + '/atlas.json'))
chunks = {}


def load(p):
    if p['chunk'] not in chunks:
        chunks[p['chunk']] = open(SRC + '/' + atlas['chunks'][p['chunk']]['url'].split('/')[-1], 'rb').read()
    b = chunks[p['chunk']]
    pos = np.frombuffer(b, np.float32, p['vertexCount'] * 3, p['positions']).reshape(-1, 3).astype(np.float64)
    nor = np.frombuffer(b, np.int16, p['vertexCount'] * 3, p['normals']).reshape(-1, 3).astype(np.float64) / 32767
    idx = np.frombuffer(b, np.uint32, p['indexCount'], p['indices']).reshape(-1, 3).astype(np.int64)
    return pos, nor, idx


# ---------- muscle name -> app key. First match wins. 'skip' = left out, 'deep' = drawn as plain muscle, not tracked. ----------
RULES = [
    (r'papillary|sphincter|perineal|coccygeus|puborectalis|arytenoid|cricothyroid|crico-arytenoid|thyro-arytenoid|vocalis|aryepiglotticus|genioglossus|hyoglossus|palatini|uvular|palpebrae|platysma|diaphragm|transversus thoracis', 'skip'),
    (r'\b(inferior|superior|lateral|medial) rectus$|\b(inferior|superior) oblique$', 'skip'),   # eye muscles
    (r'pectoralis', 'pecs'), (r'clavicular part of .*deltoid', 'delt_a'), (r'acromial part of .*deltoid', 'delt_l'), (r'spinal part of .*deltoid', 'delt_p'),
    (r'triceps brachii|anconeus', 'triceps'), (r'serratus anterior', 'serratus'),
    (r'ascending part of .*trapezius|transverse part of .*trapezius|rhomboid', 'traps_mid'), (r'descending part of .*trapezius|levator scapulae', 'traps_up'),
    (r'infraspinatus|supraspinatus|teres minor|teres major|subscapularis', 'cuff'),
    (r'biceps brachii|brachialis|coracobrachialis', 'biceps'),
    (r'brachioradialis|carpi|digitorum superficialis|digitorum profundus|extensor digitorum$|extensor digiti minimi|extensor indicis|pollicis|pronator|supinator|palmaris|of (left |right )?hand|lumbricals of hand|interossei of hand', 'forearms'),
    (r'sternocleidomastoid|scalenus|splenius|semispinalis capitis|semispinalis cervicis|longus colli|longus capitis|longissimus capitis|longissimus cervicis|rectus capitis|obliquus capitis|digastric|omohyoid|sternohyoid|sternothyroid|stylohyoid|thyrohyoid|mylohyoid|geniohyoid|iliocostalis cervicis|cervical|cervicis', 'neck'),
    (r'rectus femoris|vastus|sartorius', 'quads'), (r'adductor (brevis|longus|magnus|minimus)|gracilis|pectineus', 'adductors'),
    (r'biceps femoris|semitendinosus|semimembranosus', 'hams'), (r'gluteus maximus', 'glute_max'),
    (r'gluteus medius|gluteus minimus|tensor fasciae latae|piriformis|gemellus|obturator|quadratus femoris', 'glute_med'),
    (r'gastrocnemius|soleus|plantaris|popliteus|tibialis posterior|flexor digitorum longus|flexor hallucis longus|fibularis (longus|brevis)', 'calves'),
    (r'tibialis anterior|extensor digitorum longus|extensor hallucis longus|fibularis tertius', 'tibialis'),
    (r'external oblique', 'obliques'),
    (r'iliocostalis|longissimus thoracis|spinalis|semispinalis thoracis|rotator|intertransversari|interspinal|levatores costarum|serratus posterior', 'erectors'),
    (r'intercostal|iliacus|psoas|subclavius|of (left |right )?foot|hallucis|digitorum brevis|flexor accessorius|lumbrical|interosse', 'deep'),
]
MUSCLE_IN_SKELETAL = r'tibialis|fibularis|levator scapulae|subscapularis'
TENDON = r'calcaneal tendon|iliotibial tract|interosseous membrane|linea alba'


def classify(p):
    n, s = p['name'].lower(), p['system']
    if re.search(TENDON, n): return 'tendon'
    if s == 'muscular' or re.search(MUSCLE_IN_SKELETAL, n) or 'tensor fasciae' in n:
        for rx, key in RULES:
            if re.search(rx, n): return key
        return 'deep'
    if s == 'skeletal': return 'bone'
    return 'skip'


def cluster(pos, idx, cell):
    """Vertex clustering: snap points to a grid, merge each cell into its average, drop collapsed triangles."""
    q = np.floor(pos / cell).astype(np.int64)
    _, inv, cnt = np.unique(q, axis=0, return_inverse=True, return_counts=True)
    inv = inv.ravel()
    npos = np.zeros((len(cnt), 3)); np.add.at(npos, inv, pos); npos /= cnt[:, None]
    f = inv[idx]
    f = f[(f[:, 0] != f[:, 1]) & (f[:, 1] != f[:, 2]) & (f[:, 0] != f[:, 2])]
    if len(f):
        key = np.sort(f, axis=1); _, first = np.unique(key, axis=0, return_index=True); f = f[np.sort(first)]
    used = np.unique(f); remap = -np.ones(len(npos), np.int64); remap[used] = np.arange(len(used))
    return npos[used], remap[f]


def normals(pos, idx, hint=None):
    fn = np.cross(pos[idx[:, 1]] - pos[idx[:, 0]], pos[idx[:, 2]] - pos[idx[:, 0]])
    n = np.zeros_like(pos)
    for k in range(3): np.add.at(n, idx[:, k], fn)
    l = np.linalg.norm(n, axis=1, keepdims=True); l[l == 0] = 1
    return n / l


def fibre(pos, period=0.009, axis=None):
    """Position across the part's long axis, in stripe periods. Fibres run along the longest direction of a muscle."""
    c = pos.mean(0)
    if axis is None:
        w, v = np.linalg.eigh(np.cov((pos - c).T)); axis = v[:, 1]   # middle axis: across the muscle, in its surface
    return (pos - c) @ np.asarray(axis, float) / period


CELL = {'bone': 0.0062, 'deep': 0.006, 'tendon': 0.006}
groups = {}


def add(key, pos, idx, fib):
    g = groups.setdefault(key, {'pos': [], 'nor': [], 'idx': [], 'fib': [], 'n': 0})
    g['pos'].append(pos); g['nor'].append(normals(pos, idx)); g['idx'].append(idx + g['n']); g['fib'].append(fib); g['n'] += len(pos)


skin = None
for p in atlas['parts']:
    if p['name'] == 'Skin': skin = load(p); continue
    key = classify(p)
    if key == 'skip': continue
    pos, nor, idx = load(p)
    fib = fibre(pos) if key not in ('bone', 'tendon') and len(pos) > 3 else np.zeros(len(pos))
    c = CELL.get(key, 0.0042)
    if len(idx) > 60:
        q = np.floor(pos / c).astype(np.int64); _, inv = np.unique(q, axis=0, return_inverse=True); inv = inv.ravel()
        cpos, cidx = cluster(pos, idx, c)
        if len(cidx) >= 8:
            # carry the fibre number through the same clustering
            cf = np.zeros(inv.max() + 1); cn = np.zeros(inv.max() + 1); np.add.at(cf, inv, fib); np.add.at(cn, inv, 1); cf /= cn
            f2 = inv[idx]; f2 = f2[(f2[:, 0] != f2[:, 1]) & (f2[:, 1] != f2[:, 2]) & (f2[:, 0] != f2[:, 2])]
            used = np.unique(f2); fib = cf[used]; pos, idx = cpos, cidx
    add(key, pos, idx, fib)

# ---------- generated muscles: latissimus dorsi and rectus abdominis, cut from the skin surface and set just under it ----------
sm = lambda a, b, x: np.clip((x - a) / (b - a), 0, 1) ** 2 * (3 - 2 * np.clip((x - a) / (b - a), 0, 1))
spos, snor, sidx = skin
# The skin mesh is coarse on the trunk, so split its triangles there (each into 16) to get clean patch edges.
_c = spos[sidx].mean(1); _sel = (_c[:, 1] > 0.85) & (_c[:, 1] < 1.45) & (np.abs(_c[:, 0]) < 0.2)
tp, tn = spos[sidx[_sel]], snor[sidx[_sel]]                               # (T, 3, 3) corner positions and normals
for _ in range(2):
    m = lambda a: [(a[:, 0] + a[:, 1]) / 2, (a[:, 1] + a[:, 2]) / 2, (a[:, 2] + a[:, 0]) / 2]
    def split(a):
        ab, bc, ca = m(a)
        return np.concatenate([np.stack(t, 1) for t in ((a[:, 0], ab, ca), (ab, a[:, 1], bc), (ca, bc, a[:, 2]), (ab, bc, ca))])
    tp, tn = split(tp), split(tn)
flat = np.round(tp.reshape(-1, 3) / 1e-5).astype(np.int64)
_, first, inv = np.unique(flat, axis=0, return_index=True, return_inverse=True)
spos = tp.reshape(-1, 3)[first]; sidx = inv.ravel().reshape(-1, 3)
# The source skin is a two-sided shell, so its normals cancel out. Drop repeated triangles and turn every one to face away from the body's axis.
_, _f = np.unique(np.sort(sidx, axis=1), axis=0, return_index=True); sidx = sidx[np.sort(_f)]
_c = spos[sidx].mean(1); _fn = np.cross(spos[sidx[:, 1]] - spos[sidx[:, 0]], spos[sidx[:, 2]] - spos[sidx[:, 0]])
_flip = (_fn[:, 0] * _c[:, 0] + _fn[:, 2] * _c[:, 2]) < 0; sidx[_flip] = sidx[_flip][:, [0, 2, 1]]
snor = normals(spos, sidx)
x, y, z = spos[:, 0], spos[:, 1], spos[:, 2]; ax = np.abs(x); sx = np.sign(x) + (x == 0)
outward = snor[:, 0] * sx   # > 0 on the outer side of the trunk, < 0 on the inside of the arm


def patch(mask, depth, key, axis, period):
    keep = mask[sidx].min(1) > 0.5
    f = sidx[keep]; used = np.unique(f); remap = -np.ones(len(spos), np.int64); remap[used] = np.arange(len(used))
    pos = spos[used] - snor[used] * depth
    add(key, pos, remap[f], np.zeros(len(used)) if axis is None else (np.abs(pos[:, 0]) * axis[0] + pos[:, 1] * axis[1] + pos[:, 2] * axis[2]) / period)


trunk = (ax < 0.165) & (outward > 0.0)
back = sm(0.0, 0.35, -snor[:, 2]) + sm(0.25, 0.7, outward) * (z < 0.02)
trap_w = np.clip((y - 1.13) / 0.17, 0, 1) * 0.10                       # the trapezius covers the spine side above its lower tip
upper = 1.285 + np.clip((ax - 0.03) / 0.14, 0, 1) * 0.085              # top edge rises from the mid-back toward the armpit
lower = 1.03 + np.clip((ax - 0.05) / 0.09, 0, 1) * 0.02                 # bottom edge sits on the iliac crest
apo_w = 0.012 + 0.095 * sm(1.21, 1.03, y)                               # the white lumbar aponeurosis widens toward the pelvis
zlim = -0.055 + 0.07 * sm(1.05, 1.30, y)                                # the free front edge: only the back low down, round to the side near the armpit
lats = trunk & (back > 0.5) & (y < upper) & (y > lower) & (ax > np.maximum(trap_w, apo_w)) & (z < zlim)
patch(lats.astype(float), 0.004, 'lats', (0.62, 0.78, 0), 0.010)
apo = trunk & (snor[:, 2] < -0.3) & (y < 1.21) & (y > 1.0) & (ax <= apo_w + 0.004)
patch(apo.astype(float), 0.0045, 'tendon', None, 1)
abs_w = 0.048 + 0.012 * sm(0.95, 1.2, y)
rect = (snor[:, 2] > 0.35) & (z > 0.05) & (ax > 0.007) & (ax < abs_w) & (y > 0.9) & (y < 1.265)
patch(rect.astype(float), -0.001, 'abs', (0, 1, 0), 0.058)

# ---------- write the GLB ----------
bin_ = bytearray(); views = []; accs = []; meshes = []; nodes = []


def view(data, target=None):
    while len(bin_) % 4: bin_.append(0)
    v = {'buffer': 0, 'byteOffset': len(bin_), 'byteLength': len(data)}
    if target: v['target'] = target
    bin_.extend(data); views.append(v); return len(views) - 1


total = 0
for key in sorted(groups):
    g = groups[key]
    pos = np.vstack(g['pos']).astype(np.float32); nor = np.vstack(g['nor']); idx = np.vstack(g['idx']).astype(np.uint32); fib = np.concatenate(g['fib']).astype(np.float32)
    n8 = np.zeros((len(nor), 4), np.int8); n8[:, :3] = np.clip(np.round(nor * 127), -127, 127)
    a = {'POSITION': len(accs)}
    accs.append({'bufferView': view(pos.tobytes(), 34962), 'componentType': 5126, 'count': len(pos), 'type': 'VEC3', 'min': pos.min(0).tolist(), 'max': pos.max(0).tolist()})
    a['NORMAL'] = len(accs); v = view(n8.tobytes(), 34962); views[v]['byteStride'] = 4
    accs.append({'bufferView': v, 'componentType': 5120, 'normalized': True, 'count': len(pos), 'type': 'VEC3'})
    if key not in ('bone', 'tendon'):
        a['_FIB'] = len(accs); accs.append({'bufferView': view(fib.tobytes(), 34962), 'componentType': 5126, 'count': len(pos), 'type': 'SCALAR'})
    small = len(pos) < 65535
    accs.append({'bufferView': view((idx.astype(np.uint16) if small else idx).tobytes(), 34963), 'componentType': 5123 if small else 5125, 'count': idx.size, 'type': 'SCALAR'})
    meshes.append({'name': key, 'primitives': [{'attributes': a, 'indices': len(accs) - 1}]}); nodes.append({'name': key, 'mesh': len(meshes) - 1})
    total += len(idx); print(f'{key:10s} {len(pos):7d} verts {len(idx):7d} tris')
while len(bin_) % 4: bin_.append(0)
gltf = {'asset': {'version': '2.0', 'generator': 'health-os tools/anatomy/build_body.py',
                  'copyright': 'Anatomy: BodyParts3D, (c) The Database Center for Life Science, CC BY 4.0. Simplified and regrouped; latissimus dorsi and rectus abdominis generated from the skin surface.'},
        'scene': 0, 'scenes': [{'nodes': list(range(len(nodes)))}], 'nodes': nodes, 'meshes': meshes, 'accessors': accs, 'bufferViews': views, 'buffers': [{'byteLength': len(bin_)}]}
js = json.dumps(gltf, separators=(',', ':')).encode(); js += b' ' * (-len(js) % 4)
with open(OUT, 'wb') as f:
    f.write(struct.pack('<4sII', b'glTF', 2, 12 + 8 + len(js) + 8 + len(bin_))); f.write(struct.pack('<I4s', len(js), b'JSON')); f.write(js); f.write(struct.pack('<I4s', len(bin_), b'BIN\0')); f.write(bin_)
print('total', total, 'tris,', (12 + 16 + len(js) + len(bin_)) // 1024, 'KB')

# ---------- quick software preview (front and back), to check the build without a browser ----------
if PREVIEW:
    from PIL import Image
    COL = {'bone': (226, 216, 196), 'tendon': (235, 232, 222), 'deep': (120, 52, 46)}
    H, Wd = 900, 420; img = np.zeros((H, Wd * 2, 3), np.uint8) + 14
    for view_i, sgn in enumerate((1, -1)):
        zb = np.full((H, Wd), -1e9); im = np.zeros((H, Wd, 3)) + 14
        for ki, key in enumerate(sorted(groups)):
            g = groups[key]; pos = np.vstack(g['pos']); nor = np.vstack(g['nor']); idx = np.vstack(g['idx'])
            base = np.array(COL.get(key, (176 + (ki * 37) % 40, 62 + (ki * 53) % 30, 52)), float)
            # sample each triangle at 4 points for coverage
            for wts in ((1/3, 1/3, 1/3), (.6, .2, .2), (.2, .6, .2), (.2, .2, .6), (.45, .45, .1), (.1, .45, .45), (.45, .1, .45), (.8, .1, .1), (.1, .8, .1), (.1, .1, .8)):
                c = sum(pos[idx[:, k]] * wts[k] for k in range(3)); n = sum(nor[idx[:, k]] * wts[k] for k in range(3))
                px = ((c[:, 0] * sgn) * 480 + Wd / 2).astype(int); py = (H - 20 - c[:, 1] * 500).astype(int); d = c[:, 2] * sgn
                ok = (px >= 0) & (px < Wd - 2) & (py >= 0) & (py < H - 2)
                lam = np.clip(n[:, 2] * sgn * 0.75 + n[:, 1] * 0.25 + 0.25, 0.12, 1)
                for dx in (0, 1, 2):
                    for dy in (0, 1, 2):
                        X, Y = px[ok] + dx, py[ok] + dy; D = d[ok]; C = base * lam[ok][:, None]
                        o = np.argsort(D); X, Y, D, C = X[o], Y[o], D[o], C[o]
                        m = D > zb[Y, X]; zb[Y[m], X[m]] = D[m]; im[Y[m], X[m]] = C[m]
        img[:, view_i * Wd:(view_i + 1) * Wd] = np.clip(im, 0, 255)
    Image.fromarray(img).save(PREVIEW)
