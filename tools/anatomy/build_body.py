"""Build the Body tab's anatomical model (models/body.glb) from Z-Anatomy.

Source: Z-Anatomy, "the libre 3D atlas of anatomy" (github.com/Z-Anatomy/Models-of-human-anatomy), CC BY-SA 4.0, itself derived from
BodyParts3D (c) The Database Center for Life Science. The model this script writes is a derivative work and carries the same licence.

    python3 tools/anatomy/extract_zanatomy.py Z-Anatomy/Startup.blend z.npz        # reads the Blender file directly; Blender is not needed
    python3 tools/anatomy/build_body.py z.npz models/body.glb [preview.png]

What it does:
  1. keeps the skeleton, the muscles and a few tendon sheets; drops the fascia layers that would cover the muscles, and everything in the head
  2. sorts every muscle into one of the app's muscle keys by its name
  3. evens out the detail: very dense parts are thinned, coarse muscles are subdivided and rounded (Loop subdivision) so they have no flat facets
  4. bakes three numbers into every muscle point for the app's shader: a fibre number, a groove shade and an occlusion shade
  5. makes the head, hands and feet as plain smooth shapes
  6. writes one mesh per muscle key, plus 'bone', 'tendon', 'deep' (muscles shown but not tracked) and 'head' (the plain shapes)
"""
import re, struct, sys, json
import numpy as np
from scipy.spatial import cKDTree, ConvexHull

SRC, OUT = sys.argv[1], sys.argv[2]
PREVIEW = sys.argv[3] if len(sys.argv) > 3 else None
sm = lambda a, b, x: np.clip((x - a) / (b - a), 0, 1) ** 2 * (3 - 2 * np.clip((x - a) / (b - a), 0, 1))

# ---------- load: Blender's frame is Z up with the front toward -Y; the app's is Y up with the front toward +Z ----------
Z = np.load(SRC); _o = np.concatenate([[0], np.cumsum(Z['nv'])]); _t = np.concatenate([[0], np.cumsum(Z['nt'])])
PARTS = []
for i, (name, path) in enumerate(zip(Z['names'], Z['paths'])):
    p = Z['pos'][_o[i]:_o[i + 1]].astype(np.float64); PARTS.append((str(name), str(path), np.stack([p[:, 0], p[:, 2], -p[:, 1]], 1), Z['tri'][_t[i]:_t[i + 1]].astype(np.int64)))

# ---------- muscle name -> app key. First match wins. 'skip' = left out, 'deep' = drawn as plain muscle, not tracked. ----------
TENDON = r'iliotibial tract|calcaneal tendon|linea alba|posterior layer of thoracolumbar fascia|tendon of extensor digitorum longus'
# Sheets that wrap or line the muscles (they would hide them), fluid sacs, and muscles of the throat, pelvis floor and inner trunk wall.
LEFT_OUT = (r'fascia(?!e latae)|bursa|sheath|septum|retinacul|ligament|aponeurosis|tarsus|tendinous|tendon|arch\b|trochlea|pharyn|palato|glossus|arytenoid|cricothyroid|epiglott'
            r'|levator ani|anal|coccyge|pubo|internal intercostal|innermost intercostal|internal abdominal oblique|transversus|diaphragm|platysma|palpebrae')
RULES = [
    (r'pectoralis minor', 'deep'), (r'pectoralis', 'pecs'), (r'clavicular part of deltoid', 'delt_a'), (r'acromial part of deltoid', 'delt_l'), (r'spinal part of deltoid', 'delt_p'),
    (r'triceps brachii|anconeus', 'triceps'), (r'serratus anterior', 'serratus'), (r'latissimus dorsi', 'lats'),
    (r'ascending part of trapezius|transverse part of trapezius|rhomboid', 'traps_mid'), (r'descending part of trapezius|levator scapulae', 'traps_up'),
    (r'infraspinatus|supraspinatus|teres minor|teres major|subscapularis', 'cuff'),
    (r'biceps brachii|brachialis|coracobrachialis', 'biceps'),
    (r'brachioradialis|carpi|digitorum superficialis|digitorum profundus|extensor digitorum$|extensor digiti minimi$|extensor indicis|pollicis|pronator|supinator|palmaris|of hand', 'forearms'),
    (r'sternocleidomastoid|scalenus|splenius|capitis|colli|digastric|omohyoid|sternohyoid|sternothyroid|stylohyoid|thyrohyoid|mylohyoid|geniohyoid', 'neck'),
    (r'rectus femoris|vastus|sartorius', 'quads'), (r'adductor (brevis|longus|magnus|minimus)|gracilis|pectineus', 'adductors'),
    (r'biceps femoris|semitendinosus|semimembranosus', 'hams'), (r'gluteus maximus', 'glute_max'),
    (r'gluteus medius|gluteus minimus|tensor fasciae latae|piriformis|gemellus|obturator|quadratus femoris', 'glute_med'),
    (r'gastrocnemius|soleus|plantaris|popliteus|tibialis posterior|flexor digitorum longus|flexor hallucis longus|fibularis (longus|brevis)', 'calves'),
    (r'tibialis anterior|extensor digitorum longus|extensor hallucis longus|fibularis tertius', 'tibialis'),
    (r'rectus abdominis|pyramidalis', 'abs'), (r'external abdominal oblique', 'obliques'),
    (r'iliocostalis|longissimus thoracis|spinalis|semispinalis|multifidus|rotator|intertransversari|interspinal|levatores|serratus posterior|quadratus lumborum', 'erectors'),
]
HEAD_BONES = r'parietal|frontal|occipital|sphenoid|ethmoid|mandible|temporal bone|concha|lacrimal|nasal|vomer|maxilla|palatine|zygomatic|malleus|incus|stapes|alar cartilage|molar|incisor|canine|tooth'
THROAT = r'hyoid bone|thyroid cartilage|cricoid|arytenoid cartilage|corniculate'
HEAD_Y = 1.49           # a muscle (other than a neck muscle) that sits wholly above this height belongs to the face or scalp


def bounds(name):
    i = [n for n, *_ in PARTS].index(name); return PARTS[i][2].min(0), PARTS[i][2].max(0)
WRIST_Y = bounds('Radius.l')[0][1] + 0.004; ANKLE_Y = bounds('Tibia.l')[0][1]; HAND_X = 0.17


def classify(name, path, pos):
    n = re.sub(r'\.[lr]$', '', name).lower(); lo, hi = pos.min(0), pos.max(0)
    if hi[1] < WRIST_Y - 0.01 and np.abs(pos[:, 0]).min() > HAND_X: return 'hand'      # wholly inside a hand: replaced by the plain hand shape
    if hi[1] < ANKLE_Y + 0.012: return 'foot'
    if path.startswith('1'):
        if re.search(HEAD_BONES, n) and lo[1] > 1.40: return 'headbone'
        return 'skip' if re.search(THROAT, n) else 'bone'
    if not path.startswith('4'): return 'skip'
    if re.search(TENDON, n): return 'tendon'
    if re.search(LEFT_OUT, n): return 'skip'
    # The source file has the names of the upper and lower trapezius swapped (its "ascending part" is the one on the neck), so go by height.
    if 'trapezius' in n and 'transverse' not in n: return 'traps_up' if pos[:, 1].mean() > 1.40 else 'traps_mid'
    for rx, key in RULES:
        if re.search(rx, n): return 'headmuscle' if key != 'neck' and lo[1] > HEAD_Y else key
    return 'headmuscle' if lo[1] > HEAD_Y else 'deep'


def pack(a):
    """One whole number per row of small whole numbers, so rows can be compared and grouped quickly."""
    a = np.asarray(a, np.int64); k = np.zeros(len(a), np.int64)
    for c in range(a.shape[1]): k = (k << (21 if a.shape[1] > 2 else 31)) | (a[:, c] + (1 << 20 if a.shape[1] > 2 else 0))
    return k


def weld(pos, idx, tol=2e-4):
    """Points that share a place become one point; collapsed and repeated triangles go."""
    _, first, inv = np.unique(pack(np.round(pos / tol)), return_index=True, return_inverse=True)
    f = inv.ravel()[idx]; f = f[(f[:, 0] != f[:, 1]) & (f[:, 1] != f[:, 2]) & (f[:, 0] != f[:, 2])]
    used = np.unique(f); remap = -np.ones(len(first), np.int64); remap[used] = np.arange(len(used)); return pos[first][used], remap[f]


def thin_out(pos, idx, cell):
    """Simplify by merging the points inside each grid cell into their average. Points are only merged when their surfaces face the same
    way, so the two faces of a thin sheet stay apart and the sheet does not collapse into holes."""
    n = normals(pos, idx)
    q = pack(np.floor(pos / cell)) * 8 + (n > 0).astype(np.int64) @ np.array([1, 2, 4])
    _, inv, cnt = np.unique(q, return_inverse=True, return_counts=True); inv = inv.ravel()
    npos = np.zeros((len(cnt), 3)); np.add.at(npos, inv, pos); npos /= cnt[:, None]
    f = inv[idx]; f = f[(f[:, 0] != f[:, 1]) & (f[:, 1] != f[:, 2]) & (f[:, 0] != f[:, 2])]
    if len(f): _, first = np.unique(pack(np.sort(f, axis=1)), return_index=True); f = f[np.sort(first)]
    used = np.unique(f); remap = -np.ones(len(npos), np.int64); remap[used] = np.arange(len(used)); return npos[used], remap[f]


def loop_subdivide(pos, idx):
    """One round of Loop subdivision: every triangle becomes four and all points are moved onto a smooth surface through the old shape.
    This is what turns a faceted, low-detail muscle into a rounded one."""
    e = np.concatenate([idx[:, [0, 1]], idx[:, [1, 2]], idx[:, [2, 0]]]); opp = np.concatenate([idx[:, 2], idx[:, 0], idx[:, 1]])
    key = np.sort(e, axis=1); _, first, inv, cnt = np.unique(pack(key), return_index=True, return_inverse=True, return_counts=True); inv = inv.ravel(); ue = key[first]
    osum = np.zeros((len(ue), 3)); np.add.at(osum, inv, pos[opp])
    inner = cnt == 2
    mid = (pos[ue[:, 0]] + pos[ue[:, 1]]) / 2; mid[inner] = (pos[ue[inner, 0]] + pos[ue[inner, 1]]) * 0.375 + osum[inner] * 0.125
    # old points: inner points move toward the average of their neighbours, edge points along their edge only
    nb = np.zeros_like(pos); deg = np.zeros(len(pos)); np.add.at(nb, ue[:, 0], pos[ue[:, 1]]); np.add.at(nb, ue[:, 1], pos[ue[:, 0]]); np.add.at(deg, ue[:, 0], 1); np.add.at(deg, ue[:, 1], 1)
    onb = np.zeros(len(pos), bool); be = ue[~inner]; onb[be.ravel()] = True
    bsum = np.zeros_like(pos); bdeg = np.zeros(len(pos)); np.add.at(bsum, be[:, 0], pos[be[:, 1]]); np.add.at(bsum, be[:, 1], pos[be[:, 0]]); np.add.at(bdeg, be[:, 0], 1); np.add.at(bdeg, be[:, 1], 1)
    d = np.maximum(deg, 1); beta = np.where(d == 3, 3 / 16, 3 / (8 * d)); new = pos * (1 - d * beta)[:, None] + nb * beta[:, None]
    two = onb & (bdeg == 2); new[two] = pos[two] * 0.75 + bsum[two] * 0.125; odd = onb & ~two; new[odd] = pos[odd]
    m = len(pos) + inv.reshape(3, -1).T                                    # midpoint index of each triangle's three edges (ab, bc, ca)
    a, b_, c_ = idx[:, 0], idx[:, 1], idx[:, 2]; ab, bc, ca = m[:, 0], m[:, 1], m[:, 2]
    return np.vstack([new, mid]), np.vstack([np.stack([a, ab, ca], 1), np.stack([ab, b_, bc], 1), np.stack([ca, bc, c_], 1), np.stack([ab, bc, ca], 1)])


def edge_len(pos, idx):
    return float(np.mean([np.linalg.norm(pos[idx[:, k]] - pos[idx[:, (k + 1) % 3]], axis=1).mean() for k in range(3)]))


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


groups = {}


def add(key, pos, idx, fib, ao=None, tend=None, tint=0.5):
    g = groups.setdefault(key, {'pos': [], 'nor': [], 'idx': [], 'fib': [], 'ao': [], 'tend': [], 'tint': [], 'n': 0})
    g['pos'].append(pos); g['nor'].append(normals(pos, idx)); g['idx'].append(idx + g['n']); g['fib'].append(fib)
    g['ao'].append(np.ones(len(pos)) if ao is None else ao); g['tend'].append(np.zeros(len(pos)) if tend is None else tend)
    g['tint'].append(np.full(len(pos), tint)); g['n'] += len(pos)


# Broad, flat muscles attach along a wide edge, not through a cord: they only get a faint pale band there.
FLAT = ('pecs', 'lats', 'traps_mid', 'traps_up', 'glute_max', 'glute_med', 'obliques', 'serratus', 'abs', 'erectors', 'neck', 'cuff')


def bulk_up(pos, idx, key, bone_tree, bone_pts):
    """Give a muscle more mass: its belly is pushed outward, away from the bone it lies on, most at its thickest part and not at all at
    its ends, so the attachments stay where they are. Only the side facing away from the bone moves, so the muscle grows outward
    instead of sinking into its neighbours. Thick muscles gain the most; broad flat ones get a gentler, even swell."""
    c = pos.mean(0); w, v = np.linalg.eigh(np.cov((pos - c).T)); t = (pos - c) @ v[:, 2]; lo, hi = t.min(), t.max()
    if hi - lo < 0.06: return pos
    u = (t - lo) / (hi - lo); r = np.linalg.norm((pos - c) - np.outer(t, v[:, 2]), axis=1); mid = sm(0.04, 0.3, np.minimum(u, 1 - u))
    if key in FLAT: amount = (0.009 if key in ('glute_max', 'pecs') else 0.005) * mid
    else:
        NB = 24; bi = np.minimum((u * NB).astype(int), NB - 1); rb = np.array([np.percentile(r[bi == k], 80) if (bi == k).sum() > 2 else np.nan for k in range(NB)])
        ok = ~np.isnan(rb); rb = np.interp(np.arange(NB), np.arange(NB)[ok], rb[ok]); rb = np.convolve(np.pad(rb, 1, mode='edge'), np.ones(3) / 3, 'valid')
        girth = np.interp(u * NB - 0.5, np.arange(NB), rb) / rb.max(); amount = np.clip(0.30 * rb.max(), 0.002, 0.0115) * sm(0.3, 0.95, girth) * mid
    n = normals(pos, idx); out = pos - bone_pts[bone_tree.query(pos)[1]]; out /= np.linalg.norm(out, axis=1, keepdims=True) + 1e-9
    return pos + n * (amount * np.clip((n * out).sum(1), 0, 1))[:, None]


def tendon_ends(pos, flat=False):
    """How tendon-like each point of a muscle is, 0 (red belly) to 1 (pale tendon). A muscle turns to tendon toward its two ends, and
    most of all where it narrows into a cord; a broad flat muscle only gets a faint pale band along its attachments."""
    c = pos.mean(0); w, v = np.linalg.eigh(np.cov((pos - c).T)); t = (pos - c) @ v[:, 2]; lo, hi = t.min(), t.max(); length = hi - lo
    if length < 0.05: return np.zeros(len(pos))
    u = (t - lo) / length; r = np.linalg.norm((pos - c) - np.outer(t, v[:, 2]), axis=1)
    NB = 24; bi = np.minimum((u * NB).astype(int), NB - 1); rb = np.array([np.percentile(r[bi == k], 80) if (bi == k).sum() > 2 else np.nan for k in range(NB)])
    ok = ~np.isnan(rb); rb = np.interp(np.arange(NB), np.arange(NB)[ok], rb[ok]); rb = np.convolve(np.pad(rb, 1, mode='edge'), np.ones(3) / 3, 'valid')
    girth = np.interp(u * NB - 0.5, np.arange(NB), rb) / rb.max()                 # 1 at the thickest part of the belly
    end = 1 - sm(0.02, 0.17, np.minimum(u, 1 - u)); thin = 1 - sm(0.22, 0.55, girth)
    if flat: return 0.32 * (1 - sm(0.0, 0.07, np.minimum(u, 1 - u)))
    return np.clip(end * (0.3 + 0.7 * thin) + 0.85 * thin * sm(0.5, 0.2, np.minimum(u, 1 - u)), 0, 1)


# ---------- every part: sort, even out its detail, bake fibre and groove numbers ----------
FINE, COARSE = 0.0050, 0.0098       # muscles denser than FINE are thinned to it; muscles coarser than COARSE are subdivided
COVERED = ('erectors', 'deep', 'neck')   # groups of many small or mostly covered parts: kept lighter
# muscles that lie under other muscles and are rarely seen: kept lighter too
BURIED = (r'tibialis posterior|flexor digitorum longus|flexor hallucis longus|popliteus|vastus intermedius|adductor (brevis|minimus)|obturator|gemellus|quadratus femoris|piriformis'
          r'|gluteus minimus|subscapularis|supinator|pronator quadratus|digitorum profundus|flexor pollicis longus|multifidus|rotator|interspinal|intertransvers|levatores|psoas|iliacus')
head_pts, hand_bones, foot_bones = [], {}, {}
_bones = np.vstack([q for nm, pth, q, _ in PARTS if classify(nm, pth, q) == 'bone']); _bone_tree = cKDTree(_bones)
for name, path, pos, idx in PARTS:
    key = classify(name, path, pos)
    if key in ('headbone', 'headmuscle'): head_pts.append(pos); continue
    side = 'l' if pos[:, 0].mean() > 0 else 'r'
    if key == 'hand':
        if path.startswith('1'): hand_bones.setdefault(side, []).append((name.lower(), pos))
        continue
    if key == 'foot':
        if path.startswith('1'): foot_bones.setdefault(side, []).append(pos)
        continue
    if key == 'skip': continue
    pos, idx = weld(pos, idx)
    if len(idx) < 8: continue
    soft = key not in ('bone', 'tendon'); L = edge_len(pos, idx); size = np.linalg.norm(pos.max(0) - pos.min(0))
    if 'intercostal' in name.lower(): cell = 0.0085                       # between the ribs, mostly hidden
    elif key == 'bone': cell = min(0.0072, size / 18)
    elif key == 'tendon': cell = 0.0058
    else: cell = min(0.0076 if key in COVERED or re.search(BURIED, name.lower()) else FINE, size / 24)
    if L < cell * 0.93: pos, idx = thin_out(pos, idx, cell)
    elif soft and key not in COVERED and not re.search(BURIED, name.lower()):
        while edge_len(pos, idx) > COARSE and len(idx) < 60000: pos, idx = loop_subdivide(pos, idx)
    if len(idx) < 8: continue
    if soft and key not in COVERED and not re.search(BURIED, name.lower()): pos = bulk_up(pos, idx, key, _bone_tree, _bones)
    fib = fibre(pos) if soft else np.zeros(len(pos))
    tint = (int.from_bytes(re.sub(r'\.[lr]$', '', name).encode()[-6:], 'little') * 2654435761 % 1000) / 1000   # the same on both sides of the body
    add(key, pos, idx, fib, cavity(pos, idx) if len(idx) > 20 else None, tendon_ends(pos, key in FLAT) if soft and key != 'deep' else None, tint)


# ---------- uncover the abs ----------
# The external oblique ends in a flat tendon sheet that runs across the front of the rectus abdominis (the front of the "rectus sheath").
# Drawn as it is, it hides the six-pack, so the part of that sheet lying directly over the rectus is cut away.
_abs = np.vstack(groups['abs']['pos']); _tree = cKDTree(_abs); _g = groups['obliques']; _off = 0
for i in range(len(_g['pos'])):
    P = _g['pos'][i]; d, j = _tree.query(P); over = (d < 0.011) & (P[:, 2] > _abs[j][:, 2] - 0.002) & (np.abs(P[:, 0]) < np.abs(_abs[:, 0]).max() + 0.004)
    f = _g['idx'][i] - _off; _g['idx'][i] = f[~over[f].all(1)] + _off; _off += len(P)

# ---------- the head, hands and feet: plain smooth shapes ----------
def blob(points, grow, nu=40, nv=26, rounds=8):
    """A smooth closed shape around a set of points: their convex hull (which bridges every hollow), pushed out by `grow` metres,
    rebuilt as an even ball of points and smoothed."""
    hull = ConvexHull(points); c = points[hull.vertices].mean(0); eq = hull.equations; bn, bd = eq[:, :3], -(eq[:, 3] + eq[:, :3] @ c) + grow
    th = np.linspace(0, np.pi, nv + 1)[1:-1]; ph = np.linspace(0, 2 * np.pi, nu, endpoint=False)
    dirs = np.vstack([[0, 1, 0], [[np.sin(t) * np.cos(f), np.cos(t), np.sin(t) * np.sin(f)] for t in th for f in ph], [0, -1, 0]])
    nd = dirs @ bn.T; nd[nd < 1e-9] = 1e-9; p = c + dirs * (bd[None, :] / nd).min(1)[:, None]
    f = []; ring = lambda i, j: 1 + i * nu + j % nu; last = len(p) - 1
    for j in range(nu):
        f.append([0, ring(0, j + 1), ring(0, j)]); f.append([last, ring(nv - 2, j), ring(nv - 2, j + 1)])
        for i in range(nv - 2): f += [[ring(i, j), ring(i, j + 1), ring(i + 1, j)], [ring(i, j + 1), ring(i + 1, j + 1), ring(i + 1, j)]]
    f = np.array(f); p = smooth(p, f, rounds); add('head', p, f, np.zeros(len(p)))


blob(np.vstack(head_pts), 0.006, 48, 32, 12)
ORDINAL = ('first', 'second', 'third', 'fourth', 'fifth')
for side, bones in hand_bones.items():
    palm = [p for n, p in bones if 'phalanx' not in n and 'first metacarpal' not in n]
    blob(np.vstack(palm), 0.0105, 28, 18, 6)
    for k, o in enumerate(ORDINAL):                                      # the thumb takes its metacarpal with it; each finger is its three bones
        digit = [p for n, p in bones if ('phalanx of ' + o) in n or (k == 0 and 'first metacarpal' in n)]
        if digit: blob(np.vstack(digit), 0.0048, 14, 18, 4)
for side, bones in foot_bones.items(): blob(np.vstack(bones), 0.009, 36, 22, 8)


# ---------- occlusion shade: how hemmed-in each muscle point is by the surfaces around it ----------
# From a spot a little above each point (along its outward direction), count how much nearby surface faces that spot. Out on the open top
# of a muscle there is only the muscle's own surface below; down in the furrow between two muscles there are walls on both sides. Points
# that see more surface are drawn darker, which is what separates one muscle from the next at a glance.
import os
if os.environ.get('QUICK'): groups_ao_skip = True
rng = np.random.default_rng(1); S_P, S_N = [], []; DENS = 1 / (2.6e-3) ** 2          # sample points per square metre of surface
for key, g in groups.items():
    P = np.vstack(g['pos']); I = np.vstack(g['idx']); a, b_, c_ = P[I[:, 0]], P[I[:, 1]], P[I[:, 2]]
    fn = np.cross(b_ - a, c_ - a); area = np.linalg.norm(fn, axis=1) / 2; cnt = rng.poisson(area * DENS); t = np.repeat(np.arange(len(I)), cnt)
    u, v = rng.random(len(t)), rng.random(len(t)); flip = u + v > 1; u[flip], v[flip] = 1 - u[flip], 1 - v[flip]
    S_P.append(a[t] + (b_[t] - a[t]) * u[:, None] + (c_[t] - a[t]) * v[:, None]); S_N.append(fn[t] / (2 * area[t, None] + 1e-20))
S_P, S_N = np.vstack(S_P), np.vstack(S_N); tree = cKDTree(S_P); UP, R = 0.006, 0.009; flat = DENS * np.pi * (R * R - UP * UP)
for key, g in groups.items():
    if key in ('head', 'tendon'): continue
    for i in range(len(g['pos'])):
        q = g['pos'][i] + g['nor'][i] * UP; seen = np.zeros(len(q))
        for s in range(0, len(q), 20000):
            nb = tree.query_ball_point(q[s:s + 20000], R); lens = np.array([len(x) for x in nb]); flat_i = np.concatenate(nb).astype(np.int64) if lens.sum() else np.zeros(0, np.int64)
            own = np.repeat(np.arange(len(lens)), lens); facing = ((q[s:s + 20000][own] - S_P[flat_i]) * S_N[flat_i]).sum(1) > 0
            seen[s:s + 20000] = np.bincount(own[facing], minlength=len(lens))
        occ = 1 - 0.72 * sm(1.25, 3.4, seen / flat)
        # even the shade out over each point's neighbours, so one stray sample (where two muscles touch) does not leave a dark fleck
        f = g['idx'][i] - sum(len(q) for q in g['pos'][:i]); e = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]); e = np.concatenate([e, e[:, ::-1]])
        deg = np.bincount(e[:, 0], minlength=len(occ)).astype(float); deg[deg == 0] = 1
        for _ in range(4):
            acc = np.zeros(len(occ)); np.add.at(acc, e[:, 0], occ[e[:, 1]]); occ = 0.4 * occ + 0.6 * acc / deg
        g['ao'][i] = g['ao'][i] * occ

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
    if key != 'head':   # three shades per point, one byte each: occlusion, tendon-ness, and a tint that differs from one muscle to the next
        a4 = np.zeros((len(pos), 4), np.uint8); a4[:, 0] = ao
        a4[:, 1] = np.clip(np.round(np.concatenate(g['tend']) * 255), 0, 255); a4[:, 2] = np.clip(np.round(np.concatenate(g['tint']) * 255), 0, 255)
        a['_AO'] = len(accs); v = view(a4.tobytes(), 34962); views[v]['byteStride'] = 4
        accs.append({'bufferView': v, 'componentType': 5121, 'normalized': True, 'count': len(pos), 'type': 'VEC3'})
    small = len(pos) < 65535
    accs.append({'bufferView': view((idx.astype(np.uint16) if small else idx).tobytes(), 34963), 'componentType': 5123 if small else 5125, 'count': idx.size, 'type': 'SCALAR'})
    meshes.append({'name': key, 'primitives': [{'attributes': a, 'indices': len(accs) - 1}]})
    nodes.append({'name': key, 'mesh': len(meshes) - 1, 'translation': lo.tolist(), 'scale': span.tolist()})
    total += len(idx); print(f'{key:10s} {len(pos):7d} verts {len(idx):7d} tris')
while len(bin_) % 4: bin_.append(0)
gltf = {'asset': {'version': '2.0', 'generator': 'health-os tools/anatomy/build_body.py',
                  'copyright': 'Anatomy: Z-Anatomy, the libre 3D atlas of anatomy (CC BY-SA 4.0), derived from BodyParts3D (c) The Database Center for Life Science. This file is a derivative work (regrouped, simplified, smoothed; head, hands and feet replaced by plain shapes) and is licensed CC BY-SA 4.0.'},
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
