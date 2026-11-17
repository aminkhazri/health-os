"""Draw frames of a clip without a browser or a graphics card, to check poses while building them.

It does what the app's 3D viewer does, in plain numpy: work out where every bone is at a moment in the clip, move each point
of the surface with the bones it is attached to ("skinning"), then paint the triangles back to front.

Usage: python3 preview.py <model.glb> <clip> <out.png> [view=three|front|side|back] [t0,t1,...  as fractions of the clip]
"""
import sys, numpy as np
from PIL import Image, ImageDraw
from scipy.spatial.transform import Rotation as R
import glbio
from mannequin import raw

def pose_matrices(j, b, clip, frac):
    N = j['nodes']; n = len(N); T = np.zeros((n, 3)); Q = np.tile([0, 0, 0, 1.0], (n, 1))
    for i, nd in enumerate(N): T[i] = nd.get('translation', [0, 0, 0]); Q[i] = nd.get('rotation', [0, 0, 0, 1])
    an = next(a for a in j['animations'] if a['name'] == clip)
    for c in an['channels']:
        s = an['samplers'][c['sampler']]; t = glbio.acc(j, b, s['input'])[:, 0]; o = glbio.acc(j, b, s['output'])
        x = frac * t[-1]; k = int(np.clip(np.searchsorted(t, x) - 1, 0, max(0, len(t) - 2))); u = 0 if len(t) < 2 else np.clip((x - t[k]) / (t[k + 1] - t[k] or 1), 0, 1)
        v0, v1 = o[k], o[min(k + 1, len(o) - 1)]
        if c['target']['path'] == 'rotation':
            if v0 @ v1 < 0: v1 = -v1
            v = v0 + (v1 - v0) * u; Q[c['target']['node']] = v / np.linalg.norm(v)
        elif c['target']['path'] == 'translation': T[c['target']['node']] = v0 + (v1 - v0) * u
    par = {c: i for i, nd in enumerate(N) for c in nd.get('children', [])}; M = [None] * n
    def world(i):
        if M[i] is None:
            m = np.eye(4); m[:3, :3] = R.from_quat(Q[i]).as_matrix(); m[:3, 3] = T[i]; M[i] = world(par[i]) @ m if i in par else m
        return M[i]
    return [world(i) for i in range(n)]

def skinned(j, b, clip, frac):
    p = j['meshes'][0]['primitives'][0]; at = p['attributes']; V = raw(j, b, at['POSITION'])[0].astype(float); F = raw(j, b, p['indices'])[0].astype(int).reshape(-1, 3)
    J = raw(j, b, at['JOINTS_0'])[0].astype(int); Wt, wa = raw(j, b, at['WEIGHTS_0']); Wt = Wt.astype(float); Wt /= Wt.sum(1, keepdims=True)
    sk = j['skins'][0]; ibm = raw(j, b, sk['inverseBindMatrices'])[0].reshape(-1, 4, 4).transpose(0, 2, 1); M = pose_matrices(j, b, clip, frac)
    skin = np.stack([M[n] @ ibm[k] for k, n in enumerate(sk['joints'])]); Vh = np.c_[V, np.ones(len(V))]
    out = np.zeros((len(V), 3))
    for k in range(4): out += Wt[:, k:k + 1] * np.einsum('nij,nj->ni', skin[J[:, k]], Vh)[:, :3]
    return out, F

def paint(V, F, view, size=(300, 400), box=None):
    a = {'front': 0.0, 'three': 0.75, 'side': np.pi / 2, 'back': np.pi * 0.85}[view]; c, s = np.cos(a), np.sin(a)
    x = V[:, 0] * c - V[:, 2] * s; y = V[:, 1]; z = V[:, 0] * s + V[:, 2] * c; W, H = size
    lo, hi = box if box else (-0.05, 1.8); sc = H * 0.94 / (hi - lo); px = x * sc + W / 2; py = H - ((y - lo) * sc + H * 0.03)
    Q = np.stack([x, y, z], 1); tri = Q[F]; n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]); n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-9
    L = unit = np.array([0.35, 0.55, 0.75]); L = L / np.linalg.norm(L); sh = np.clip(n @ L, 0, 1) * 0.75 + 0.25
    im = Image.new('RGB', size, (30, 36, 46)); d = ImageDraw.Draw(im)
    for i in np.argsort(tri[:, :, 2].mean(1)):
        if n[i, 2] <= 0: continue
        g = int(228 * sh[i]); p0, p1, p2 = F[i]; d.polygon([(px[p0], py[p0]), (px[p1], py[p1]), (px[p2], py[p2])], fill=(g, g, int(g * 0.97)))
    return im

if __name__ == '__main__':
    j, b = glbio.load(sys.argv[1]); clip, out = sys.argv[2], sys.argv[3]; views = (sys.argv[4] if len(sys.argv) > 4 else 'three').split(',')
    fr = [float(x) for x in (sys.argv[5] if len(sys.argv) > 5 else '0,0.2,0.44,0.7').split(',')]
    tiles = [paint(*skinned(j, b, clip, f), v) for v in views for f in fr]; w, h = tiles[0].size
    sheet = Image.new('RGB', (w * len(fr), h * len(views)))
    for k, t in enumerate(tiles): sheet.paste(t, ((k % len(fr)) * w, (k // len(fr)) * h))
    sheet.save(out); print('wrote', out)
