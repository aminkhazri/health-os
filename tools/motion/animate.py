"""Hand-built animation clips for the Health OS mannequin.

A move is described the way a coach would: where the hips go, how far the trunk leans, where the feet and hands are.
For every frame (30 a second) this script then works out each bone's rotation:

  * trunk bones are tilted directly;
  * arms and legs are solved backwards from where the hand or foot must be ("inverse kinematics", IK): given the hip and
    the ankle, there is only one place the knee can be once you say which way it points;
  * feet that are planted never move, which is what makes the motion look grounded.

Movement between key moments follows a "minimum jerk" curve: it starts and stops gently, like a real limb does.

Usage: python3 animate.py <athlete.glb> <out.glb> [move name ...]
"""
import sys, numpy as np
from scipy.spatial.transform import Rotation as R
import glbio
from retarget import Skel

X, Y, Z = np.eye(3)
BONES = ['Hips', 'Spine', 'Spine1', 'Spine2', 'Neck', 'Head'] + [s + b for s in ('Left', 'Right') for b in ('Shoulder', 'Arm', 'ForeArm', 'Hand', 'UpLeg', 'Leg', 'Foot', 'ToeBase')]
def unit(v): v = np.asarray(v, float); return v / (np.linalg.norm(v) or 1.0)
def pitch(deg): return R.from_rotvec(X * np.radians(deg))     # lean forward (the body faces +Z)
def basis(d, hinge):
    """A full orientation: the bone's length runs along d, and it bends about the hinge."""
    y = unit(d); x = unit(hinge - (hinge @ y) * y); return R.from_matrix(np.column_stack([x, y, np.cross(x, y)]))
def ease(u): u = min(1.0, max(0.0, u)); return u * u * u * (10 - 15 * u + 6 * u * u)   # minimum-jerk: gentle start, gentle stop

class Body:
    def __init__(self, j):
        self.T = T = Skel(j); self.rest = {b: T.world(b) for b in BONES}            # world position and rotation at rest
        self.off = {b: np.array(T.N[T.idx[b]].get('translation', [0, 0, 0]), float) for b in BONES}
        self.parent = {b: T.N[T.par[T.idx[b]]].get('name') for b in BONES}
        p = lambda b: self.rest[b][0]
        self.len = {s + a: np.linalg.norm(p(s + b) - p(s + a)) for s in ('Left', 'Right') for a, b in (('Arm', 'ForeArm'), ('ForeArm', 'Hand'), ('UpLeg', 'Leg'), ('Leg', 'Foot'))}
        # how each limb bone sits relative to "points along d, bends about hinge" at rest; knees bend about the left-right axis, elbows too
        self.fit = {}
        for s, sx in (('Left', 1), ('Right', -1)):
            for b, hinge in (('UpLeg', -X), ('Leg', -X), ('Arm', -X), ('ForeArm', -X), ('Hand', np.array([-sx, 0, 0]))):
                q = self.rest[s + b][1]; self.fit[s + b] = (basis(q.apply(Y), hinge).inv() * q)

    def limb(self, a, t, l1, l2, pole):
        """Two-bone IK. From joint a to target t with bone lengths l1, l2; the middle joint is pushed toward 'pole'. Returns (middle joint, hinge axis)."""
        d = t - a; L = min(np.linalg.norm(d), (l1 + l2) * 0.999); u = unit(d); p = unit(pole - (pole @ u) * u)
        c = (l1 * l1 + L * L - l2 * l2) / (2 * l1 * L); k = np.sqrt(max(0.0, 1 - c * c))
        return a + l1 * (c * u + k * p), unit(np.cross(u, p))

    def solve(self, P):
        """P describes one frame. Returns ({bone: local rotation}, hips position)."""
        W, pos = {}, {}
        def place(b):
            par = self.parent[b]; pos[b] = pos[par] + W[par].apply(self.off[b]) if par in W else np.array(P['hips'], float)
        lean = 0.0
        for b, key in (('Hips', 'pelvis'), ('Spine', 'spine'), ('Spine1', 'spine1'), ('Spine2', 'chest'), ('Neck', 'neck'), ('Head', 'head')):
            lean += P.get(key, 0.0); place(b); W[b] = pitch(lean) * self.rest[b][1]
        chest = pitch(sum(P.get(k, 0.0) for k in ('pelvis', 'spine', 'spine1', 'chest')))
        P['_chest'] = (pos['Spine2'], chest)
        for s, sx in (('Left', 1), ('Right', -1)):
            place(s + 'Shoulder'); W[s + 'Shoulder'] = chest * self.rest[s + 'Shoulder'][1]
            place(s + 'Arm'); t = np.asarray(P['hand'](s, sx, pos['Spine2'], chest), float)
            el, h = self.limb(pos[s + 'Arm'], t, self.len[s + 'Arm'], self.len[s + 'ForeArm'], np.asarray(P['elbow'](s, sx, chest), float))
            W[s + 'Arm'] = basis(el - pos[s + 'Arm'], h) * self.fit[s + 'Arm']; place(s + 'ForeArm')
            W[s + 'ForeArm'] = basis(t - el, h) * self.fit[s + 'ForeArm']; place(s + 'Hand')
            fingers, palm = P['palm'](s, sx, chest); W[s + 'Hand'] = basis(fingers, palm) * self.fit[s + 'Hand']
            place(s + 'UpLeg'); ankle = np.asarray(P['foot'](s, sx), float)
            kn, h = self.limb(pos[s + 'UpLeg'], ankle, self.len[s + 'UpLeg'], self.len[s + 'Leg'], np.asarray(P['knee'](s, sx), float))
            W[s + 'UpLeg'] = basis(kn - pos[s + 'UpLeg'], h) * self.fit[s + 'UpLeg']; place(s + 'Leg')
            W[s + 'Leg'] = basis(ankle - kn, h) * self.fit[s + 'Leg']
            W[s + 'Foot'] = self.rest[s + 'Foot'][1]; W[s + 'ToeBase'] = self.rest[s + 'ToeBase'][1]     # planted flat
        local = {b: ((W[self.parent[b]].inv() if self.parent[b] in W else R.identity()) * W[b]).as_quat() for b in BONES}
        return local, pos['Hips']

# ---------------------------------------------------------------------------------------------------- the moves
def goblet_squat(B, heel=0.0):
    """Down for 2.2 s, pause, drive up, stand tall: the same timing as the captions in the app (5 s per rep)."""
    hip0 = B.rest['Hips'][0]; ankle = {s: B.rest[s + 'Foot'][0] for s in ('Left', 'Right')}
    def depth(t):
        if t < 2.2: return ease(t / 2.2)
        if t < 2.9: return 1.0 + 0.025 * np.sin(np.pi * (t - 2.2) / 0.7)        # settle a touch deeper at the bottom, then come back
        if t < 4.3: return 1.0 - ease((t - 2.9) / 1.4)
        return 0.0
    def frame(t):
        s = depth(t); breathe = 0.004 * np.sin(2 * np.pi * t / 5.0)
        return {
            'hips': hip0 + np.array([0, -0.335 * s + breathe, -0.215 * s]),       # hips travel back and down: sitting between the heels
            'pelvis': 30 * s, 'spine': 5 * s, 'spine1': -3 * s, 'chest': -6 * s,   # the trunk leans from the hips while the chest stays proud
            'neck': -8 * s, 'head': -10 * s,                                      # eyes stay on the horizon
            'foot': lambda S, sx: ankle[S],
            'knee': lambda S, sx: np.array([sx * 0.55, 0.0, 1.0]),                # knees track out over the toes
            'hand': lambda S, sx, c, q: c + q.apply([sx * 0.085, 0.05, 0.2]),  # both hands cup the weight at the chest
            'elbow': lambda S, sx, q: q.apply([sx * 0.25, -1.0, -0.15]),          # elbows tucked, pointing down
            'palm': lambda S, sx, q: (q.apply([-sx * 0.1, 0.85, 0.5]), np.array([-sx, 0.0, 0.0])),
        }
    return 5.0, frame

MOVES = {'Goblet squat': goblet_squat}

def main(src, out, names):
    j, b = glbio.load(src); B = Body(j)
    for name in names or MOVES:
        dur, frame = MOVES[name](B); times = np.arange(0, dur + 1e-6, 1 / 30)
        rot = {x: [] for x in BONES}; hp = []
        for t in times:
            local, hips = B.solve(frame(min(t, dur - 1e-6)))
            for x in BONES: rot[x].append(local[x])
            hp.append(hips)
        par = B.T.world(B.parent['Hips'])
        glbio.add_clip(j, b, {x: B.T.idx[x] for x in BONES}, times, rot, [par[1].inv().apply(p - par[0]) for p in hp], name)
        print('clip', name, 'frames', len(times), 'seconds', dur)
    glbio.save(out, j, b); print('wrote', out)

if __name__ == '__main__': main(sys.argv[1], sys.argv[2], sys.argv[3:])
