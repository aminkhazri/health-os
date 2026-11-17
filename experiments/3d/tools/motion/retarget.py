"""Copy an animation clip from one skeleton onto the Health OS mannequin and save it inside the model file.

Why this is needed: the free clip was made for a different skeleton (other bone names, other proportions, arms out in a T
instead of our relaxed A). "Retargeting" re-expresses each frame of the clip for our bones:

  1. For every frame, work out which way each source bone points in the world.
  2. Turn the matching bone of our skeleton to point the same way (ALIGN makes up for the two skeletons resting differently).
  3. Move the hips along the same path, scaled by leg length, then keep the feet and hands on the floor.
  4. Write the result into the .glb as an animation the app can play.

Usage: python3 retarget.py <source.glb> <clip name> <athlete.glb> <out.glb> <name for the clip in the app> [--hands-down]
"""
import sys, numpy as np
from scipy.spatial.transform import Rotation as R
import glbio

MAP = {'Hips': 'pelvis', 'Spine': 'spine_01', 'Spine1': 'spine_02', 'Spine2': 'spine_03', 'Neck': 'neck_01', 'Head': 'head'}
for S, s in (('Left', 'l'), ('Right', 'r')):
    MAP.update({S + 'Shoulder': 'clavicle_' + s, S + 'Arm': 'upperarm_' + s, S + 'ForeArm': 'lowerarm_' + s, S + 'Hand': 'hand_' + s,
                S + 'UpLeg': 'thigh_' + s, S + 'Leg': 'calf_' + s, S + 'Foot': 'foot_' + s, S + 'ToeBase': 'ball_' + s})
UP = np.array([0.0, 1.0, 0.0])   # both files come from Blender, where a bone's own Y axis runs along the bone

class Skel:
    def __init__(self, j):
        self.N = j['nodes']; self.idx = {n.get('name'): i for i, n in enumerate(self.N)}
        self.par = {c: i for i, n in enumerate(self.N) for c in n.get('children', [])}
    def rest(self, i): n = self.N[i]; return np.array(n.get('translation', [0, 0, 0]), float), R.from_quat(n.get('rotation', [0, 0, 0, 1]))
    def world(self, name, rot=None, pos=None):
        """World position and rotation of a bone; rot/pos override the rest pose for the named bones."""
        chain, i = [], self.idx[name]
        while i is not None: chain.append(i); i = self.par.get(i)
        p, q = np.zeros(3), R.identity()
        for i in reversed(chain):
            t, r = self.rest(i); nm = self.N[i].get('name')
            if rot and nm in rot: r = rot[nm]
            if pos and nm in pos: t = pos[nm]
            p = p + q.apply(t); q = q * r
        return p, q

def arc(a, b):
    """Smallest rotation that turns direction a into direction b."""
    a, b = a / np.linalg.norm(a), b / np.linalg.norm(b); ax = np.cross(a, b); s = np.linalg.norm(ax)
    return R.identity() if s < 1e-8 else R.from_rotvec(ax / s * np.arctan2(s, a @ b))

def main(src_path, clip, tgt_path, out_path, out_name, hands_down=False):
    sj, sb = glbio.load(src_path); tj, tb = glbio.load(tgt_path); S, T = Skel(sj), Skel(tj)
    an = next(a for a in sj['animations'] if a['name'] == clip)
    times = max((glbio.acc(sj, sb, s['input'])[:, 0] for s in an['samplers']), key=len); F = len(times)
    srot, spos = {}, {}
    for c in an['channels']:
        s = an['samplers'][c['sampler']]; v = glbio.acc(sj, sb, s['output']); nm = S.N[c['target']['node']].get('name')
        if len(v) != F: v = np.repeat(v[:1], F, axis=0)          # a channel with a single held value
        if c['target']['path'] == 'rotation': srot[nm] = v
        elif c['target']['path'] == 'translation': spos[nm] = v
    # rest-pose bookkeeping
    s0 = {b: S.world(s) for b, s in MAP.items()}; t0 = {b: T.world(b) for b in MAP}
    align = {b: arc(t0[b][1].apply(UP), s0[b][1].apply(UP)) for b in MAP}
    scale = t0['LeftUpLeg'][0][1] / s0['LeftUpLeg'][0][1]         # hip-joint height: ours over theirs
    order = sorted(MAP, key=lambda b: depth(T, b))                 # parents before children
    out_rot = {b: np.zeros((F, 4)) for b in MAP}; out_pos = np.zeros((F, 3)); floor = []
    hips_parent = T.N[T.par[T.idx['Hips']]].get('name')
    for f in range(F):
        rot = {n: R.from_quat(v[f]) for n, v in srot.items()}; pos = {n: v[f] for n, v in spos.items()}
        tw = {}
        for b in order:
            _, sw = S.world(MAP[b], rot, pos)
            tw[b] = sw * s0[b][1].inv() * align[b] * t0[b][1]     # same change of direction as the source bone, applied to ours
        local = {}
        for b in order:
            p = T.N[T.par[T.idx[b]]].get('name'); pw = tw[p] if p in tw else T.world(p)[1]
            local[b] = pw.inv() * tw[b]; out_rot[b][f] = local[b].as_quat()
        hp, _ = S.world('pelvis', rot, pos); pp, pq = T.world(hips_parent)
        out_pos[f] = pq.inv().apply(hp * scale - pp)
    # keep contact with the floor: measure where our toes and wrists end up, then lift/tilt the whole body to suit
    def fk(f, name): return T.world(name, {b: R.from_quat(out_rot[b][f]) for b in MAP}, {'Hips': out_pos[f]})[0]
    rest_toe = min(t0['LeftToeBase'][0][1], t0['RightToeBase'][0][1])
    for f in range(F):
        toe = min(fk(f, 'LeftToeBase')[1], fk(f, 'RightToeBase')[1]); out_pos[f][1] += rest_toe - toe
    if hands_down:   # hands planted too (push-ups, planks): our arms are a different length, so tip the body about the toes until the wrists sit at palm height
        for f in range(F):
            toe = (fk(f, 'LeftToeBase') + fk(f, 'RightToeBase')) / 2; hand = (fk(f, 'LeftHand') + fk(f, 'RightHand')) / 2
            tilt = R.from_rotvec([-(0.035 - hand[1]) / (hand[2] - toe[2]), 0, 0])
            out_pos[f] = toe + tilt.apply(out_pos[f] - toe); out_rot['Hips'][f] = (tilt * R.from_quat(out_rot['Hips'][f])).as_quat()
    report = [(round(float(times[f]), 2), np.round(fk(f, 'LeftHand'), 3), np.round(fk(f, 'LeftToeBase'), 3), np.round(fk(f, 'Hips'), 3), np.round(fk(f, 'Head'), 3)) for f in (0, F // 4, F // 2, 3 * F // 4, F - 1)]
    for r in report: print(' t', r[0], 'hand', r[1], 'toe', r[2], 'hips', r[3], 'head', r[4])
    glbio.add_clip(tj, tb, {b: T.idx[b] for b in MAP}, times - times[0], out_rot, out_pos, out_name)
    glbio.save(out_path, tj, tb); print('wrote', out_path, 'clip', out_name, 'frames', F, 'seconds', round(float(times[-1] - times[0]), 2), 'scale', round(float(scale), 3))

def depth(T, b):
    d, i = 0, T.idx[b]
    while i in T.par: i = T.par[i]; d += 1
    return d

if __name__ == '__main__': main(*sys.argv[1:6], hands_down='--hands-down' in sys.argv)
