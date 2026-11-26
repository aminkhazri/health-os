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
    (r'pectoralis minor', 'deep'), (r'pectoralis', 'pecs'), (r'clavicular part of .*deltoid', 'delt_a'), (r'acromial part of .*deltoid', 'delt_l'), (r'spinal part of .*deltoid', 'delt_p'),
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
# The head is drawn as one smooth plain shape (made from the skin, below), so the skull, teeth and throat cartilages are left out.
HEAD_PARTS = r'frontal bone|parietal bone|temporal bone|occipital bone|sphenoid|ethmoid|maxilla|mandible|zygomatic|nasal|palatine bone|vomer|lacrimal|concha|tooth|gingiva|hyoid|cricoid|thyroid cartilage|arytenoid|corniculate|cuneiform cartilage|alar cartilage|epiglott|ossicle|malleus|incus|stapes'
HEAD_Y = 1.535          # a muscle that sits wholly above this height is inside the head
TENDON = r'calcaneal tendon|iliotibial tract|interosseous membrane|linea alba'


def classify(p):
    n, s = p['name'].lower(), p['system']
    if re.search(TENDON, n): return 'tendon'
    if s == 'muscular' or re.search(MUSCLE_IN_SKELETAL, n) or 'tensor fasciae' in n:
        if p['bounds'][0][1] > HEAD_Y: return 'skip'
        for rx, key in RULES:
            if re.search(rx, n): return key
        return 'deep'
    if s == 'skeletal': return 'skip' if re.search(HEAD_PARTS, n) or p['bounds'][0][1] > 1.6 else 'bone'
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


def smooth(pos, idx, rounds, keep=None):
    """Taubin smoothing (a shrink step then a swell step, so the shape keeps its size). Points flagged in `keep` stay put."""
    e = np.concatenate([idx[:, [0, 1]], idx[:, [1, 2]], idx[:, [2, 0]]]); e = np.concatenate([e, e[:, ::-1]])
    deg = np.bincount(e[:, 0], minlength=len(pos)).astype(float); deg[deg == 0] = 1; q = pos.copy()
    for i in range(rounds * 2):
        acc = np.zeros_like(q); np.add.at(acc, e[:, 0], q[e[:, 1]]); nq = q + (acc / deg[:, None] - q) * (0.6 if i % 2 == 0 else -0.62)
        if keep is not None: nq[keep] = q[keep]
        q = nq
    return q


def fibre(pos, period=0.009, axis=None):
    """Fibre number of every point: its position across the muscle, counted in fibre-bundle widths. The app draws a bundle per whole number.
    Fibres run along the muscle's long axis, so "across" means going round the muscle. Each point gets the distance round the muscle's
    outline (seen end-on, down the long axis), measured from the side that faces into the body. That keeps the bundles running along the
    muscle on every side you can look at it from, flat or rounded, and lets them draw together toward the tendon ends."""
    c = pos.mean(0)
    if axis is not None: return (pos - c) @ np.asarray(axis, float) / period
    w, v = np.linalg.eigh(np.cov((pos - c).T)); long_ = v[:, 2]
    out = np.array([c[0], 0.0, c[2]]); out = out - (out @ long_) * long_
    if np.linalg.norm(out) < 0.03:                                        # on the midline, or lying along the outward direction: use the thin axis
        out = v[:, 0] * (1 if v[:, 0] @ np.array([c[0], 0.0, c[2] if abs(c[2]) > 0.01 else 1.0]) >= 0 else -1)
    e1 = out / np.linalg.norm(out); e2 = np.cross(long_, e1)
    q = pos - c; a_, b_ = q @ e1, q @ e2; th = np.arctan2(b_, a_); r = np.hypot(a_, b_)
    NB = 72; bi = np.minimum(((th + np.pi) / (2 * np.pi) * NB).astype(int), NB - 1); rb = np.full(NB, np.nan)
    for k in range(NB):
        m = bi == k
        if m.sum() >= 2: rb[k] = np.percentile(r[m], 85)
    ok = ~np.isnan(rb)
    if ok.sum() < 6: return (pos - c) @ v[:, 1] / period
    cen = (np.arange(NB) + 0.5) / NB * 2 * np.pi - np.pi
    rb = np.interp(cen, np.concatenate([cen[ok] - 2 * np.pi, cen[ok], cen[ok] + 2 * np.pi]), np.tile(rb[ok], 3))
    rb = np.convolve(np.concatenate([rb[-2:], rb, rb[:2]]), np.ones(5) / 5, 'valid')
    ox, oy = rb * np.cos(cen), rb * np.sin(cen); seg = np.hypot(np.diff(ox), np.diff(oy)); arc = np.concatenate([[0], np.cumsum(seg)])
    return np.interp(th, cen, arc) / period


CELL = {'bone': 0.007, 'deep': 0.0042, 'tendon': 0.0045}   # simplification grid per kind, in metres
MUSCLE_CELL = 0.0029
groups = {}


def cavity(pos, idx, rounds=5, depth=0.0035):
    """Shade for grooves: 1 on open surface, toward 0 where a point sits below its smoothed neighbourhood (between fibre bundles, in folds).
    The app multiplies the muscle colour by it, which is what makes the bundles read as separate."""
    n = normals(pos, idx); e = np.concatenate([idx[:, [0, 1]], idx[:, [1, 2]], idx[:, [2, 0]]]); e = np.concatenate([e, e[:, ::-1]])
    deg = np.bincount(e[:, 0], minlength=len(pos)).astype(float); deg[deg == 0] = 1
    q = pos.copy()
    for _ in range(rounds):
        acc = np.zeros_like(q); np.add.at(acc, e[:, 0], q[e[:, 1]]); q = acc / deg[:, None]
    lift = ((q - pos) * n).sum(1)                 # > 0: the smoothed surface is above this point, so the point is in a groove
    return np.clip(1 - lift / depth, 0.3, 1.0)


def add(key, pos, idx, fib, ao=None):
    g = groups.setdefault(key, {'pos': [], 'nor': [], 'idx': [], 'fib': [], 'ao': [], 'n': 0})
    g['pos'].append(pos); g['nor'].append(normals(pos, idx)); g['idx'].append(idx + g['n']); g['fib'].append(fib)
    g['ao'].append(np.ones(len(pos)) if ao is None else ao); g['n'] += len(pos)


skin = None
WRIST_Y, HAND_X, ANKLE_Y = 0.888, 0.17, 0.072       # hands hang below the wrist line, out to the side; feet sit below the ankle line
inner_pts = []                                       # bone points inside the hands and feet, used to tell the skin's outside from its inside
for p in atlas['parts']:
    if p['name'] == 'Skin': skin = load(p); continue
    key = classify(p)
    if key == 'skip': continue
    (x0, y0, z0), (x1, y1, z1) = p['bounds']
    in_hand = y1 < WRIST_Y - 0.01 and min(abs(x0), abs(x1)) > HAND_X; in_foot = y1 < ANKLE_Y - 0.008
    if in_hand or in_foot:                           # wholly inside a hand or foot: covered by the plain glove shape made below
        if key == 'bone': inner_pts.append(load(p)[0])
        continue
    pos, nor, idx = load(p)
    soft = key not in ('bone', 'tendon')
    fib = fibre(pos) if soft and len(pos) > 3 else np.zeros(len(pos))
    size = np.linalg.norm(pos.max(0) - pos.min(0))
    c = min(CELL.get(key, MUSCLE_CELL), size / (28 if soft else 22))          # small parts (finger bones, thin slips) keep a finer grid so they stay whole
    if 'intercostal' in p['name'].lower(): c = 0.005        # between the ribs, mostly hidden
    # Most muscles in the source are already light, and simplifying them frays their thin edges, so they are kept exactly as drawn.
    # Only the few very dense parts (and the skeleton) are simplified.
    busy = key in ('erectors', 'deep', 'neck', 'forearms')   # groups made of many small or mostly covered parts: simplified a little
    thin = soft and not busy and 'intercostal' not in p['name'].lower()   # sheets thinner than the grid would tear, so they are never simplified
    if thin or key == 'tendon' or len(idx) <= (600 if soft else 60): c = 0.0003   # weld only: points that share a place become one
    if len(idx) > 8:
        q = np.floor(pos / c).astype(np.int64); _, inv = np.unique(q, axis=0, return_inverse=True); inv = inv.ravel()
        cpos, cidx = cluster(pos, idx, c)
        if len(cidx) >= 8:
            # carry the fibre number through the same clustering
            cf = np.zeros(inv.max() + 1); cn = np.zeros(inv.max() + 1); np.add.at(cf, inv, fib); np.add.at(cn, inv, 1); cf /= cn
            f2 = inv[idx]; f2 = f2[(f2[:, 0] != f2[:, 1]) & (f2[:, 1] != f2[:, 2]) & (f2[:, 0] != f2[:, 2])]
            used = np.unique(f2); fib = cf[used]; pos, idx = cpos, cidx
    if key == 'pecs':   # the lowest slips of the chest muscle run under the abdominal wall and poke through it as stray specks: trim them
        tc = pos[idx].mean(1); idx = idx[~((tc[:, 1] < 1.25) & (np.abs(tc[:, 0]) < 0.10))]
    add(key, pos, idx, fib, cavity(pos, idx) if soft and len(idx) > 20 else None)

# ---------- generated muscles: latissimus dorsi and rectus abdominis, cut from the skin surface and set just under it ----------
sm = lambda a, b, x: np.clip((x - a) / (b - a), 0, 1) ** 2 * (3 - 2 * np.clip((x - a) / (b - a), 0, 1))
spos, snor, sidx = skin

# ---------- hands and feet: plain smooth shapes cut from the skin, in the same style as the head ----------
from scipy.spatial import cKDTree
_c0 = spos[sidx].mean(1)
gf = sidx[((_c0[:, 1] < WRIST_Y) & (np.abs(_c0[:, 0]) > HAND_X)) | (_c0[:, 1] < ANKLE_Y)]
used = np.unique(gf); remap = -np.ones(len(spos), np.int64); remap[used] = np.arange(len(used)); gpos = spos[used].copy(); gf = remap[gf]
_, first, inv = np.unique(np.round(gpos / 2e-4).astype(np.int64), axis=0, return_index=True, return_inverse=True)
gpos = gpos[first]; gf = inv.ravel()[gf]; gf = gf[(gf[:, 0] != gf[:, 1]) & (gf[:, 1] != gf[:, 2]) & (gf[:, 0] != gf[:, 2])]
_, _f = np.unique(np.sort(gf, axis=1), axis=0, return_index=True); gf = gf[np.sort(_f)]
_tc = gpos[gf].mean(1); _near = np.vstack(inner_pts)[cKDTree(np.vstack(inner_pts)).query(_tc)[1]]
_fn = np.cross(gpos[gf[:, 1]] - gpos[gf[:, 0]], gpos[gf[:, 2]] - gpos[gf[:, 0]]); _flip = (_fn * (_tc - _near)).sum(1) < 0; gf[_flip] = gf[_flip][:, [0, 2, 1]]
gpos = smooth(gpos, gf, 3)
add('head', gpos, gf, np.zeros(len(gpos)))

# ---------- the head: one smooth, plain shape. Cut from the skin above the jaw line, then smoothed until the face has no features. ----------
_c = spos[sidx].mean(1)
_cut = lambda q: q[:, 1] > 1.512 - 0.42 * np.minimum(q[:, 2], 0.0)       # under the chin in front, rising to the base of the skull behind
hf = sidx[_cut(_c)]; _, _f = np.unique(np.sort(hf, axis=1), axis=0, return_index=True); hf = hf[np.sort(_f)]
used = np.unique(hf); remap = -np.ones(len(spos), np.int64); remap[used] = np.arange(len(used)); hpos = spos[used].copy(); hf = remap[hf]
# weld points that share a position (the source skin is a two-sided shell), then keep one copy of each triangle
_, first, inv = np.unique(np.round(hpos / 2e-4).astype(np.int64), axis=0, return_index=True, return_inverse=True)
hpos = hpos[first]; hf = inv.ravel()[hf]; hf = hf[(hf[:, 0] != hf[:, 1]) & (hf[:, 1] != hf[:, 2]) & (hf[:, 0] != hf[:, 2])]
_, _f = np.unique(np.sort(hf, axis=1), axis=0, return_index=True); hf = hf[np.sort(_f)]
hc = np.array([0.0, 1.62, 0.0]); _tc = hpos[hf].mean(1) - hc; _fn = np.cross(hpos[hf[:, 1]] - hpos[hf[:, 0]], hpos[hf[:, 2]] - hpos[hf[:, 0]])
_flip = (_fn * _tc).sum(1) < 0; hf[_flip] = hf[_flip][:, [0, 2, 1]]
hpos = smooth(hpos, hf, 40)
# No face at all: wrap the smoothed head in its convex hull (which bridges the eye sockets, mouth and ears), then rebuild it as an even
# ball of points pushed out to that hull and smooth once more. The result is a plain mannequin head of the right size and tilt.
from scipy.spatial import ConvexHull
hull = ConvexHull(hpos); hc = hpos[hull.vertices].mean(0); eq = hull.equations; bn, bd = eq[:, :3], -(eq[:, 3] + eq[:, :3] @ hc)   # planes n.x = d, measured from hc
NU, NV = 48, 32
th = np.linspace(0, np.pi, NV + 1)[1:-1]; ph = np.linspace(0, 2 * np.pi, NU, endpoint=False)
dirs = np.array([[np.sin(t) * np.cos(f), np.cos(t), np.sin(t) * np.sin(f)] for t in th for f in ph]); dirs = np.vstack([[0, 1, 0], dirs, [0, -1, 0]])
nd = dirs @ bn.T; nd[nd < 1e-9] = 1e-9; rad = (bd[None, :] / nd).min(1)
hpos = hc + dirs * rad[:, None]
hf = []; ring = lambda i, j: 1 + i * NU + j % NU; last = len(hpos) - 1
for j in range(NU):
    hf.append([0, ring(0, j + 1), ring(0, j)]); hf.append([last, ring(NV - 2, j), ring(NV - 2, j + 1)])
    for i in range(NV - 2): hf += [[ring(i, j), ring(i, j + 1), ring(i + 1, j)], [ring(i, j + 1), ring(i + 1, j + 1), ring(i + 1, j)]]
hf = np.array(hf); hpos = smooth(hpos, hf, 12)
add('head', hpos, hf, np.zeros(len(hpos)))
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


def patch(field, depth, key, axis, period, relief=None):
    """A muscle cut out of the skin surface. `field` is a number per skin point, positive inside the muscle; triangles that cross zero are
    cut along the zero line, so the outline is a clean curve and not a staircase of whole triangles."""
    fv = field[sidx]; npos = (fv > 0).sum(1)
    full = sidx[npos == 3]
    ep = {}; extra_p = []; extra_n = []; tris = []
    base = len(spos)
    def cut(i, j):   # point on edge i-j where the field is zero (i inside, j outside); one shared point per edge
        k = (min(i, j), max(i, j))
        if k not in ep:
            t = field[i] / (field[i] - field[j]); ep[k] = base + len(extra_p)
            extra_p.append(spos[i] + (spos[j] - spos[i]) * t); n = snor[i] + (snor[j] - snor[i]) * t; extra_n.append(n / (np.linalg.norm(n) or 1))
        return ep[k]
    for tri, fr in zip(sidx[(npos == 1) | (npos == 2)], fv[(npos == 1) | (npos == 2)]):
        ins = fr > 0
        if ins.sum() == 1:
            r = int(np.argmax(ins)); a, b_, c_ = tri[r], tri[(r + 1) % 3], tri[(r + 2) % 3]; tris.append([a, cut(a, b_), cut(a, c_)])
        else:
            r = int(np.argmin(ins)); a, b_, c_ = tri[r], tri[(r + 1) % 3], tri[(r + 2) % 3]; ab, ac = cut(b_, a), cut(c_, a); tris += [[ab, b_, c_], [ab, c_, ac]]
    P = np.vstack([spos] + ([np.array(extra_p)] if extra_p else [])); N = np.vstack([snor] + ([np.array(extra_n)] if extra_n else []))
    f = np.vstack([full] + ([np.array(tris)] if tris else []))
    f = f[(f[:, 0] != f[:, 1]) & (f[:, 1] != f[:, 2]) & (f[:, 0] != f[:, 2])]
    used = np.unique(f); remap = -np.ones(len(P), np.int64); remap[used] = np.arange(len(used)); f = remap[f]
    # the edge dives a little, so it tucks under the neighbouring muscles the way a real muscle border does
    e = np.sort(np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]), axis=1); ue, cnt = np.unique(e, axis=0, return_counts=True)
    ring = np.full(len(used), 99); ring[np.unique(ue[cnt == 1])] = 0
    for r in range(1, 5):
        nb = np.zeros(len(used), bool); on = ring[ue[:, 0]] == r - 1; nb[ue[on, 1]] = True; on = ring[ue[:, 1]] == r - 1; nb[ue[on, 0]] = True; ring[nb & (ring == 99)] = r
    sink = (1 - np.clip(ring / 4, 0, 1)) ** 2 * 0.010
    pos = P[used] - N[used] * (depth + sink)[:, None]
    if relief is not None: pos = pos + N[used] * relief(pos)[:, None]
    add(key, pos, f, np.zeros(len(used)) if axis is None else (np.abs(pos[:, 0]) * axis[0] + pos[:, 1] * axis[1] + pos[:, 2] * axis[2]) / period)


allof = lambda *fs: np.minimum.reduce([np.asarray(f, float) for f in fs])    # inside every one of the given limits
trunk = allof(0.165 - ax, outward)
back = sm(0.0, 0.35, -snor[:, 2]) + sm(0.25, 0.7, outward) * sm(0.03, 0.01, z) - 0.5
trap_w = np.clip((y - 1.13) / 0.17, 0, 1) * 0.10                       # the trapezius covers the spine side above its lower tip
upper = 1.285 + np.clip((ax - 0.03) / 0.14, 0, 1) * 0.085              # top edge rises from the mid-back toward the armpit
lower = 1.03 + np.clip((ax - 0.05) / 0.09, 0, 1) * 0.02                 # bottom edge sits on the iliac crest
apo_w = 0.010 + 0.05 * sm(1.19, 1.03, y)                               # the pale lumbar aponeurosis widens toward the pelvis
zlim = -0.055 + 0.07 * sm(1.05, 1.30, y)                                # the free front edge: only the back low down, round to the side near the armpit
patch(allof(trunk, back, upper - y, y - lower, ax - np.maximum(trap_w, apo_w), zlim - z), 0.004, 'lats', (0.62, 0.78, 0), 0.010)
patch(allof(trunk, -0.3 - snor[:, 2], 1.21 - y, y - 1.0, apo_w + 0.004 - ax), 0.0045, 'tendon', None, 1)
abs_w = 0.050 + 0.020 * sm(0.95, 1.22, y)                               # rectus abdominis: wider under the ribs, narrowing to the pubis
ABS_LINES = (1.222, 1.158, 1.094)                                       # the tendon bands that split the muscle into its blocks
def six_pack(q):
    """How far each point of the abs is pushed out, in metres: every block between two tendon bands swells into its own rounded pad."""
    edges = np.array([0.9, *ABS_LINES[::-1], 1.275]); k = np.clip(np.searchsorted(edges, q[:, 1]) - 1, 0, len(edges) - 2)
    v = (q[:, 1] - edges[k]) / (edges[k + 1] - edges[k]); w = 0.050 + 0.020 * sm(0.95, 1.22, q[:, 1]); u = np.clip((np.abs(q[:, 0]) - 0.006) / (w - 0.006), 0, 1)
    return 0.0055 * np.sin(np.pi * np.clip(u, 0, 1)) ** 0.55 * np.sin(np.pi * np.clip(v, 0, 1)) ** 0.55 - 0.002
patch(allof(snor[:, 2] - 0.3, z - 0.05, ax - 0.006, abs_w - ax, y - 0.9, 1.275 - y), -0.001, 'abs', (1, 0, 0), 0.0085, six_pack)
_g = groups['abs']; _p = _g['pos'][-1]; _line = np.min([np.abs(_p[:, 1] - yy) for yy in ABS_LINES], axis=0)   # tendinous intersections
_g['ao'][-1] = np.clip(0.35 + 0.65 * sm(0.0015, 0.0065, _line), 0, 1) * np.clip(0.5 + 0.5 * sm(0.007, 0.013, np.abs(_p[:, 0])), 0, 1)

# ---------- depth shade: how far each muscle point sits below the skin, compared with the muscle surface around it ----------
# Points down in the furrows between muscles sit deeper than the tops of the muscles next to them, so they are drawn darker. This is what
# separates one muscle from the next at a glance. (The generated lats and abs sit on the skin itself, so they are left out of the comparison.)
_sp, _sn, _si = skin
_w = np.array([[a, b, 1 - a - b] for a in np.linspace(0, 1, 6) for b in np.linspace(0, 1, 6) if a + b <= 1.0001])
_skin_pts = np.einsum('wk,tkd->twd', _w, _sp[_si]).reshape(-1, 3); _skin_tree = cKDTree(_skin_pts)
_real = [(k, i) for k, g in groups.items() if k not in ('bone', 'tendon', 'head') for i in range(len(g['pos'])) if not (k in ('lats', 'abs') and i == len(g['pos']) - 1)]
_all = np.vstack([groups[k]['pos'][i] for k, i in _real]); _d = _skin_tree.query(_all)[0]
_sub = np.arange(0, len(_all), 3); _dist, _nb = cKDTree(_all[_sub]).query(_all, k=24, distance_upper_bound=0.03)
_dn = np.where(np.isfinite(_dist), _d[_sub][np.minimum(_nb, len(_sub) - 1)], np.inf); _base = np.minimum(_dn.min(1), _d)
_shade = 1 - 0.7 * sm(0.002, 0.016, _d - _base); _o = 0
for k, i in _real:
    n = len(groups[k]['pos'][i]); groups[k]['ao'][i] = groups[k]['ao'][i] * _shade[_o:_o + n]; _o += n

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
    pos = np.vstack(g['pos']); nor = np.vstack(g['nor']); idx = np.vstack(g['idx']).astype(np.uint32); fib = np.concatenate(g['fib']).astype(np.float32)
    ao = np.clip(np.round(np.concatenate(g['ao']) * 255), 0, 255).astype(np.uint8)
    # positions as 16-bit numbers inside the mesh's own box (KHR_mesh_quantization): a third of the size of floats, 0.03 mm steps
    lo = pos.min(0); span = np.maximum(pos.max(0) - lo, 1e-9); q16 = np.round((pos - lo) / span * 65535).astype(np.uint16)
    p4 = np.zeros((len(pos), 4), np.uint16); p4[:, :3] = q16
    n8 = np.zeros((len(nor), 4), np.int8); n8[:, :3] = np.clip(np.round(nor * 127), -127, 127)
    a = {'POSITION': len(accs)}; v = view(p4.tobytes(), 34962); views[v]['byteStride'] = 8
    accs.append({'bufferView': v, 'componentType': 5123, 'normalized': True, 'count': len(pos), 'type': 'VEC3', 'min': q16.min(0).tolist(), 'max': q16.max(0).tolist()})   # min and max are in stored (integer) units
    a['NORMAL'] = len(accs); v = view(n8.tobytes(), 34962); views[v]['byteStride'] = 4
    accs.append({'bufferView': v, 'componentType': 5120, 'normalized': True, 'count': len(pos), 'type': 'VEC3'})
    if key not in ('bone', 'tendon', 'head'):
        a['_FIB'] = len(accs); accs.append({'bufferView': view(fib.tobytes(), 34962), 'componentType': 5126, 'count': len(pos), 'type': 'SCALAR'})
        a4 = np.zeros((len(pos), 4), np.uint8); a4[:, 0] = ao
        a['_AO'] = len(accs); v = view(a4.tobytes(), 34962); views[v]['byteStride'] = 4
        accs.append({'bufferView': v, 'componentType': 5121, 'normalized': True, 'count': len(pos), 'type': 'SCALAR'})
    small = len(pos) < 65535
    accs.append({'bufferView': view((idx.astype(np.uint16) if small else idx).tobytes(), 34963), 'componentType': 5123 if small else 5125, 'count': idx.size, 'type': 'SCALAR'})
    meshes.append({'name': key, 'primitives': [{'attributes': a, 'indices': len(accs) - 1}]})
    nodes.append({'name': key, 'mesh': len(meshes) - 1, 'translation': lo.tolist(), 'scale': span.tolist()})
    total += len(idx); print(f'{key:10s} {len(pos):7d} verts {len(idx):7d} tris')
while len(bin_) % 4: bin_.append(0)
gltf = {'asset': {'version': '2.0', 'generator': 'health-os tools/anatomy/build_body.py',
                  'copyright': 'Anatomy: BodyParts3D, (c) The Database Center for Life Science, CC BY 4.0. Simplified and regrouped; latissimus dorsi and rectus abdominis generated from the skin surface.'},
        'extensionsUsed': ['KHR_mesh_quantization'], 'extensionsRequired': ['KHR_mesh_quantization'],
        'scene': 0, 'scenes': [{'nodes': list(range(len(nodes)))}], 'nodes': nodes, 'meshes': meshes, 'accessors': accs, 'bufferViews': views, 'buffers': [{'byteLength': len(bin_)}]}
js = json.dumps(gltf, separators=(',', ':')).encode(); js += b' ' * (-len(js) % 4)
with open(OUT, 'wb') as f:
    f.write(struct.pack('<4sII', b'glTF', 2, 12 + 8 + len(js) + 8 + len(bin_))); f.write(struct.pack('<I4s', len(js), b'JSON')); f.write(js); f.write(struct.pack('<I4s', len(bin_), b'BIN\0')); f.write(bin_)
print('total', total, 'tris,', (12 + 16 + len(js) + len(bin_)) // 1024, 'KB')

# ---------- quick software preview (front and back), to check the build without a browser ----------
if PREVIEW:
    from PIL import Image
    COL = {'bone': (226, 216, 196), 'tendon': (235, 232, 222), 'deep': (120, 52, 46), 'head': (90, 100, 116)}
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
