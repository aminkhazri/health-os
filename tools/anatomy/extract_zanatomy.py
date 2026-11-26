"""Pull the muscle, fascia, bone and skin meshes out of Z-Anatomy's Startup.blend into one .npz, in the app's frame
(metres, Y up, feet on the floor, front toward +Z). usage: extract.py Startup.blend out.npz"""
import sys, re, json, numpy as np
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from blendfile import Blend

b = Blend(sys.argv[1])
def lst(first):
    p = first
    while p and p in b.blocks:
        o, f = b.at(p); yield o, f; p = b.read(o, f, 'next')
cols = {}
for p in b.by_code['GR']:
    o, f = b.at(p)
    cols[p] = (b.read(o, f, 'id.name')[2:], [b.read(o2, f2, 'ob') for o2, f2 in lst(b.read(o, f, 'gobject.first'))], [b.read(o2, f2, 'collection') for o2, f2 in lst(b.read(o, f, 'children.first'))])
def walk(p, path, out):
    nm, obs, ch = cols[p]; path = path + [nm]
    for ob in obs: out.setdefault(ob, path)
    for c in ch:
        if c in cols: walk(c, path, out)
where = {}
for p, (nm, obs, ch) in cols.items():
    if re.match(r'^(1: Skeletal|4: Muscular)', nm) or nm == 'Integument': walk(p, [], where)

parts = []; meshes = {}
for ob, path in where.items():
    if ob not in b.blocks: continue
    o, f = b.at(ob); name = b.read(o, f, 'id.name')[2:]; data = b.read(o, f, 'data')
    if b.read(o, f, 'type') != 1 or data not in b.blocks or not re.search(r'\.[lr]$|^[^.]*$', name): continue
    mo, mf = b.at(data); nv, npoly, nl = b.read(mo, mf, 'totvert'), b.read(mo, mf, 'totpoly'), b.read(mo, mf, 'totloop')
    pv, pp, pl = b.read(mo, mf, 'mvert'), b.read(mo, mf, 'mpoly'), b.read(mo, mf, 'mloop')
    own = b.owned.get(data, {})
    if npoly < 4 or not all(q in own or q in b.blocks for q in (pv, pp, pl)): continue
    if data not in meshes:
        co = b.array(pv, np.dtype([('co', '<f4', 3), ('x', 'V4')]), nv, owner=data)['co'].astype(np.float64)
        lv = b.array(pl, np.dtype([('v', '<i4'), ('e', '<i4')]), nl, owner=data)['v']
        po = b.array(pp, np.dtype([('s', '<i4'), ('n', '<i4'), ('x', 'V4')]), npoly, owner=data)
        tris = []
        for k in range(1, int(po['n'].max()) - 1):                     # fan-triangulate every polygon
            m = po['n'] > k + 1; s = po['s'][m]; tris.append(np.stack([lv[s], lv[s + k], lv[s + k + 1]], 1))
        meshes[data] = (co, np.vstack(tris).astype(np.int64))
    co, tri = meshes[data]
    M = np.array(b.read(o, f, 'obmat')).reshape(4, 4).T                 # stored column-major
    w = co @ M[:3, :3].T + M[:3, 3]
    if np.linalg.det(M[:3, :3]) < 0: tri = tri[:, [0, 2, 1]]            # a mirrored object turns its faces inside out
    parts.append((name, '/'.join(path), w, tri))

allp = np.vstack([p[2] for p in parts]); lo, hi = allp.min(0), allp.max(0); print('blender bounds', lo.round(3), hi.round(3), len(parts), 'parts', sum(len(p[3]) for p in parts), 'tris')
np.savez_compressed(sys.argv[2], names=np.array([p[0] for p in parts]), paths=np.array([p[1] for p in parts]),
                    pos=np.vstack([p[2] for p in parts]).astype(np.float32), tri=np.vstack([p[3] for p in parts]).astype(np.int32),
                    nv=np.array([len(p[2]) for p in parts]), nt=np.array([len(p[3]) for p in parts]))
