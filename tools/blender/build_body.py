# Build the Health OS athlete.
# Source body: Blender Studio "Human Base Meshes" v1.4.1, realistic male body (CC0, https://www.blender.org/download/demo-files/).
# Steps: import -> bake sculpt detail -> thin the mesh for phones -> find joints from the body's shape -> build a skeleton
#        -> automatic skin weights -> muscle shaping -> sculpted-mannequin look (smooth featureless head, matte ivory body, black shorts, bare feet) -> previews -> export GLB.
# Run it with start-builder.bat (Blender without a window) or through run.py in Blender's Text Editor. Everything printed ends up in log.txt.
import bpy, bmesh, os, glob, math
import numpy as np
from mathutils import Vector, Quaternion, Matrix

BLEND = glob.glob(os.path.join(HERE, "assets", "**", "human_base_meshes_bundle.blend"), recursive=True)[0]
OUT = HERE
BODY, SHORTS = (0.78, 0.75, 0.70, 1), (0.012, 0.012, 0.014, 1)   # linear colour values: matte ivory, black
HEM, WAIST = 0.405, 0.575   # shorts: bottom edge and waistband, as shares of body height


def reset():   # clear the scene without reloading the file (reloading would close the script that is running)
    if bpy.context.object and bpy.context.object.mode != 'OBJECT': bpy.ops.object.mode_set(mode='OBJECT')
    for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)
    for c in list(bpy.data.collections): bpy.data.collections.remove(c)
    for blk in (bpy.data.meshes, bpy.data.armatures, bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        for d in list(blk):
            if d.users == 0: blk.remove(d)


def material(name, rgba, rough=0.6, metal=0.0, glow=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True; m.diffuse_color = rgba; m.metallic = metal; m.roughness = rough
    b = m.node_tree.nodes.get("Principled BSDF")
    if b:
        b.inputs["Base Color"].default_value = rgba; b.inputs["Roughness"].default_value = rough; b.inputs["Metallic"].default_value = metal
        if glow:
            for key, val in (("Emission Color", rgba), ("Emission Strength", glow)):
                if key in b.inputs: b.inputs[key].default_value = val
    return m


def render(name, objs, ghost=False, views=(("front", (0, -1, 0)), ("side", (-1, 0, 0)), ("three", (-0.75, -0.65, 0.12)), ("back", (0.3, 1, 0.1)))):
    """Preview pictures. Cycles on the CPU, because it needs no graphics card and so also works when Blender runs without a window."""
    bpy.context.view_layer.update()
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = 12; sc.cycles.use_denoising = False; sc.cycles.max_bounces = 2
    sc.render.resolution_x = 400; sc.render.resolution_y = 660; sc.render.resolution_percentage = 100
    if not sc.world: sc.world = bpy.data.worlds.new("W")
    sc.world.use_nodes = True; bg = sc.world.node_tree.nodes.get("Background")
    if bg: bg.inputs[0].default_value = (0.22, 0.24, 0.28, 1); bg.inputs[1].default_value = 1.0
    if "PreviewSun" not in bpy.data.objects:
        sun = bpy.data.objects.new("PreviewSun", bpy.data.lights.new("PreviewSun", 'SUN')); sun.data.energy = 3.0; sun.rotation_euler = (math.radians(55), 0, math.radians(-35)); sc.collection.objects.link(sun)
    faded = []
    if ghost:   # see-through body, so the joint markers inside show
        for m in bpy.data.materials:
            b = m.node_tree.nodes.get("Principled BSDF") if m.use_nodes and m.name != "Joint" else None
            if b: faded.append(b); b.inputs["Alpha"].default_value = 0.25
    lo = Vector((1e9,) * 3); hi = Vector((-1e9,) * 3)
    for o in objs:
        for c in o.bound_box:
            w = o.matrix_world @ Vector(c); lo = Vector(map(min, lo, w)); hi = Vector(map(max, hi, w))
    mid = (lo + hi) / 2
    cam_d = bpy.data.cameras.new("pc"); cam_d.type = 'ORTHO'; cam_d.ortho_scale = (hi.z - lo.z) * 1.06
    cam = bpy.data.objects.new("pc", cam_d); sc.collection.objects.link(cam); sc.camera = cam
    for tag, d in views:
        d = Vector(d).normalized(); f = -d; right = f.cross(Vector((0, 0, 1))).normalized(); up = right.cross(f)
        cam.matrix_world = Matrix.Translation(mid + d * 10) @ Matrix((right, up, -f)).transposed().to_4x4()   # look at the body, head up
        sc.render.filepath = os.path.join(OUT, "preview_%s_%s.png" % (name, tag)); bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(cam)
    for b in faded: b.inputs["Alpha"].default_value = 1.0


# ---------------------------------------------------------------- 1. import
reset()
with bpy.data.libraries.load(BLEND, link=False) as (src, dst):
    dst.collections = [c for c in src.collections if c == "Body Male - Realistic"]
col = dst.collections[0]; bpy.context.scene.collection.children.link(col)
body = next(o for o in col.all_objects if o.name == "GEO-body_male_realistic")
eyes = [o for o in col.all_objects if ".eye." in o.name]
body.location = (0, 0, 0); bpy.context.view_layer.update()

# ---------------------------------------------------------------- 2. bake sculpt detail, then thin the mesh
mr = body.modifiers["Multires"]; print("multires total levels", mr.total_levels)
mr.levels = min(2, mr.total_levels)
dec = body.modifiers.new("Decimate", 'DECIMATE'); dec.ratio = 0.35 if mr.levels == 2 else 0.8   # keep more of the sculpt's detail: muscles and joints read as anatomy, not facets
dg = bpy.context.evaluated_depsgraph_get()
baked = bpy.data.meshes.new_from_object(body.evaluated_get(dg), depsgraph=dg)
body.modifiers.clear(); body.data = baked; body.name = "Athlete"; baked.name = "Athlete"
# a robot has no anatomy between the legs: relax that patch of surface until it is a plain, smooth pelvis
bm = bmesh.new(); bm.from_mesh(baked); zc = min(v.co.z for v in bm.verts if abs(v.co.x) < 0.008); ymid = sum(v.co.y for v in bm.verts if abs(v.co.z - zc - 0.1) < 0.02) / max(1, sum(1 for v in bm.verts if abs(v.co.z - zc - 0.1) < 0.02))
patch = [v for v in bm.verts if abs(v.co.x) < 0.085 and zc - 0.005 < v.co.z < zc + 0.16 and v.co.y < ymid]
for _ in range(40): bmesh.ops.smooth_vert(bm, verts=patch, factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
# a mannequin head. Reshaping the scanned face always left traces of a mouth and chin, so the face is not reshaped at all:
# 1) cut the old head off along a sloping line (low under the chin, higher at the back of the skull);
# 2) build a new, clean head from a sphere: an egg that narrows to a chin which sits forward and low, like a shop mannequin;
# 3) the top of the neck ends up inside the new head, so there is no seam to see. Later the whole new head is tied to the Head bone.
Ht = max(v.co.z for v in bm.verts)
head = [v for v in bm.verts if v.co.z > 0.858 * Ht]; hy = sum(v.co.y for v in head) / len(head)
CUT_P = Vector((0, hy - 0.09, 0.866 * Ht)); CUT_N = Vector((0, -0.021 * Ht, 0.18)).normalized()   # front of the body is -Y
old = [v for v in bm.verts if (v.co - CUT_P).dot(CUT_N) > 0]
bmesh.ops.delete(bm, geom=old, context='VERTS')
rim = [v for v in bm.verts if -0.03 < (v.co - CUT_P).dot(CUT_N) <= 0]          # the top of the neck: draw it in a little so none of it pokes out of the new head
rc = sum((v.co for v in rim), Vector()) / max(1, len(rim))
for v in rim:
    k = 0.14 * (1 + (v.co - CUT_P).dot(CUT_N) / 0.03); v.co.x += (rc.x - v.co.x) * k; v.co.y += (rc.y - v.co.y) * k
for _ in range(6): bmesh.ops.smooth_vert(bm, verts=rim, factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
filled = {'faces': bmesh.ops.triangle_fill(bm, edges=[e for e in bm.edges if e.is_boundary], use_beauty=True)['geom']}; filled['faces'] = [f for f in filled['faces'] if isinstance(f, bmesh.types.BMFace)]   # close the top of the neck so the body is one sealed surface
bmesh.ops.triangulate(bm, faces=filled["faces"]); inner = old
# heavy smoothing can squash faces flat, and the automatic skin weights refuse a mesh with flat faces: clean those up
bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.0006)
bmesh.ops.dissolve_degenerate(bm, edges=bm.edges[:], dist=0.0002)
bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
print("head: removed inner verts", len(inner), "closed openings with", len(filled["faces"]), "faces")
bm.to_mesh(baked); bm.free(); baked.validate(); baked.update(); print("pelvis patch verts", len(patch), "head verts", len(head))
for p in baked.polygons: p.use_smooth = True
print("mesh after bake: verts", len(baked.vertices), "polys", len(baked.polygons), "tris", sum(len(p.vertices) - 2 for p in baked.polygons))

# ---------------------------------------------------------------- 3. joints from the body's shape
def unit0(v): return v / (np.linalg.norm(v) or 1.0)
n = len(baked.vertices); co = np.empty(n * 3); baked.vertices.foreach_get("co", co); co = co.reshape(n, 3)
X, Y, Z = co[:, 0], co[:, 1], co[:, 2]; H = Ht; print("height", round(H, 3))   # full standing height, measured before the old head came off (joint heights are fractions of it)
def cen(mask, fallback=None):
    return co[mask].mean(axis=0) if mask.sum() > 3 else np.array(fallback)
def torso_y(z): return cen((abs(X) < 0.10) & (abs(Z - z) < 0.02), (0, 0, z))[1]
crotch = Z[abs(X) < 0.008].min(); print("crotch z", round(crotch, 3))
J = {}
hipc = cen((X > 0.02) & (X < 0.22) & (Z > crotch - 0.06) & (Z < crotch - 0.02))
J["UpLeg"] = np.array([hipc[0] * 0.92, hipc[1] + 0.005, 0.52 * H])   # hip joint height: a little over half of body height
kz = 0.285 * H; kc = cen((X > 0.01) & (X < 0.3) & (abs(Z - kz) < 0.015)); J["Leg"] = np.array([kc[0], kc[1] + 0.008, kz])
ac = cen((X > 0.01) & (X < 0.3) & (abs(Z - 0.085) < 0.012)); J["Foot"] = np.array([ac[0], ac[1], 0.078])
foot = (X > 0.01) & (X < 0.3) & (Z < 0.05); toe_y = Y[foot].min(); fx = cen(foot & (Y < toe_y + 0.09))[0]
J["ToeBase"] = np.array([fx, toe_y + 0.065, 0.018]); J["ToeEnd"] = np.array([fx, toe_y + 0.005, 0.014])
# arm: fingertip = farthest point out to the side; follow the arm's centre line back from there
top = Z[(X > 0.15) & (X < 0.20)].max(); S0 = np.array([0.168, torso_y(top - 0.05) + 0.01, top - 0.048])
armv = ((X > 0.22) & (Z > 0.40 * H)) | ((X > 0.15) & (Z > top - 0.12))   # the hanging arm, without the leg below it
tip = co[armv][np.argmax(np.linalg.norm(co[armv] - S0, axis=1))]
axis = tip - S0; L = np.linalg.norm(axis); axis /= L; t = (co - S0) @ axis; r = np.linalg.norm((co - S0) - np.outer(t, axis), axis=1)
def arm_at(d): return cen(armv & (abs(t - d) < 0.018) & (r < 0.10), S0 + axis * d)
wrist_d = L - 0.108 * H; el_d = wrist_d * 0.555
J["Arm"] = S0; J["ForeArm"] = arm_at(el_d); J["Hand"] = arm_at(wrist_d); J["HandEnd"] = arm_at(wrist_d + 0.085)
J["Shoulder"] = np.array([0.03, S0[1] - 0.02, S0[2] + 0.03])
# hand: the four fingers share one chain of three bones (they close together round a handle), the thumb has two bones of its own
Lh = L - wrist_d; fwd = np.array([0.0, -1.0, 0.0]); fwd = unit0(fwd - (fwd @ axis) * axis)          # "forward" across the palm: pinky ... index ... thumb
handv = armv & (t > wrist_d + 0.01); fc = (co - J["Hand"]) @ fwd
def slab(d): m = handv & (abs(t - d) < 0.008) & (fc < np.percentile(fc[handv], 80)); return np.median(co[m], axis=0) if m.sum() > 3 else S0 + axis * d
J["F2"] = slab(wrist_d + 0.76 * Lh); J["F3"] = slab(wrist_d + 0.89 * Lh); J["FEnd"] = slab(wrist_d + 0.975 * Lh)
J["F1"] = J["F2"] - unit0(J["F3"] - J["F2"]) * 0.24 * Lh
J["FEnd"] = J["F3"] + unit0(J["F3"] - J["F2"]) * 0.11 * Lh
ttip = co[handv][np.argmax(fc[handv])]; tbase = J["Hand"] + axis * 0.16 * Lh + fwd * 0.022
def near(p): m = handv & (np.linalg.norm(co - p, axis=1) < 0.016); return np.median(co[m], axis=0) if m.sum() > 3 else p
J["T1"] = near(tbase); J["T2"] = near(tbase + (ttip - tbase) * 0.58); J["TEnd"] = tbase + (ttip - tbase) * 0.95
print("hand length", round(Lh, 3), "thumb tip", np.round(ttip, 3))
print("arm length", round(L, 3), "tip", np.round(tip, 3))
spine = {"Hips": 0.555, "Spine": 0.61, "Spine1": 0.67, "Spine2": 0.735, "Neck": 0.858, "Head": 0.912}
C = {k: np.array([0, torso_y(f * H) + (0.02 if k in ("Neck", "Head") else 0.012), f * H]) for k, f in spine.items()}
head_y = C["Head"][1]                      # middle of the head, front to back (used for the hairline)
C["Head"][1] = C["Neck"][1] - 0.012        # the neck bone stands nearly upright, so "neck straight up" in the app means looking ahead, not up
C["HeadEnd"] = np.array([0, C["Head"][1], H])
for k, v in list(J.items()) + list(C.items()): print("  joint", k, np.round(v, 3))

# ---------------------------------------------------------------- 3b. clothing edges: cut the surface along hems so colour boundaries are clean lines
def unit(v): return v / np.linalg.norm(v)
CUTS = [((0, 0, f * H), (0, 0, 1)) for f in (HEM, WAIST)]
bm = bmesh.new(); bm.from_mesh(baked)
for pco, pno in CUTS:
    bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=pco, plane_no=pno, dist=0.0003)
bm.to_mesh(baked); bm.free(); baked.validate(); baked.update()
for p in baked.polygons: p.use_smooth = True
n = len(baked.vertices); co = np.empty(n * 3); baked.vertices.foreach_get("co", co); co = co.reshape(n, 3); X, Y, Z = co[:, 0], co[:, 1], co[:, 2]
print("after clothing cuts: verts", n)

# ---------------------------------------------------------------- 4. skeleton (same bone names the app already steers)
arm_d = bpy.data.armatures.new("Rig"); rig = bpy.data.objects.new("Rig", arm_d); bpy.context.scene.collection.objects.link(rig)
bpy.context.view_layer.objects.active = rig; bpy.ops.object.mode_set(mode='EDIT')
def bone(name, head, tail, parent=None):
    b = arm_d.edit_bones.new(name); b.head = Vector(head); b.tail = Vector(tail)
    if parent: b.parent = arm_d.edit_bones[parent]
    return b
chain = ["Hips", "Spine", "Spine1", "Spine2", "Neck", "Head"]
for i, k in enumerate(chain): bone(k, C[k], C[chain[i + 1]] if i + 1 < len(chain) else C["HeadEnd"], chain[i - 1] if i else None)
for side, sx in (("Left", 1), ("Right", -1)):
    m = lambda v: (v[0] * sx, v[1], v[2])
    bone(side + "Shoulder", m(J["Shoulder"]), m(J["Arm"]), "Spine2"); bone(side + "Arm", m(J["Arm"]), m(J["ForeArm"]), side + "Shoulder")
    bone(side + "ForeArm", m(J["ForeArm"]), m(J["Hand"]), side + "Arm"); bone(side + "Hand", m(J["Hand"]), m(J["HandEnd"]), side + "ForeArm")
    bone(side + "Fingers1", m(J["F1"]), m(J["F2"]), side + "Hand"); bone(side + "Fingers2", m(J["F2"]), m(J["F3"]), side + "Fingers1"); bone(side + "Fingers3", m(J["F3"]), m(J["FEnd"]), side + "Fingers2")
    bone(side + "UpLeg", m(J["UpLeg"]), m(J["Leg"]), "Hips"); bone(side + "Leg", m(J["Leg"]), m(J["Foot"]), side + "UpLeg")
    bone(side + "Foot", m(J["Foot"]), m(J["ToeBase"]), side + "Leg"); bone(side + "ToeBase", m(J["ToeBase"]), m(J["ToeEnd"]), side + "Foot")
bpy.ops.object.mode_set(mode='OBJECT')

# ---------------------------------------------------------------- 5. skin weights
for o in bpy.context.scene.objects: o.select_set(False)
body.select_set(True); rig.select_set(True); bpy.context.view_layer.objects.active = rig
try:
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')
except Exception as e:
    print("auto weights raised", e)
print("vertex groups:", len(body.vertex_groups), "armature mods:", [m.type for m in body.modifiers])
gi = {g.index: g.name for g in body.vertex_groups}
W = {name: np.zeros(n) for name in gi.values()}
for v in baked.vertices:
    for g in v.groups: W[gi[g.group]][v.index] = g.weight
unweighted = int((sum(W.values()) < 1e-4).sum()) if W else n
print("unweighted verts:", unweighted)
if 0 < unweighted <= n * 0.02:   # a few stray points the solver skipped: tie each to the bone it sits on, so it cannot be left behind when the body moves
    total = sum(W.values())
    for v in baked.vertices:
        if total[v.index] < 1e-4:
            name = "Head" if v.co.z > 0.86 * H else "Hips"
            body.vertex_groups[name].add([v.index], 1.0, 'REPLACE'); W[name][v.index] = 1.0
if unweighted > n * 0.02: raise RuntimeError("automatic skin weights failed: the model would not move with its skeleton")
# fingers: the automatic weights only catch the fingers a bone runs through, so the four fingers are weighted by rule instead.
# Finding them: past the knuckle line each finger is its own separate island of the surface. The four islands that reach furthest
# are the fingers (the thumb is shorter and is left as part of the hand). Each finger point then follows the finger bone for its
# stretch of the finger, blending over a few millimetres at each joint.
fu = unit0(J["F3"] - J["F1"]); cm = co.copy(); cm[:, 0] = np.abs(cm[:, 0]); tm = (cm - S0) @ axis
sf = (cm - J["F1"]) @ fu; hand_m = ((cm[:, 0] > 0.22) & (cm[:, 2] > 0.40 * H)) & (tm > wrist_d + 0.01)
k2, k3 = float((J["F2"] - J["F1"]) @ fu), float((J["F3"] - J["F1"]) @ fu); blend = lambda x: np.clip(x / 0.012 + 0.5, 0, 1)
ev = np.empty(len(baked.edges) * 2, dtype=np.int64); baked.edges.foreach_get("vertices", ev); ev = ev.reshape(-1, 2)
nbr = {}
for a_, b_ in ev[hand_m[ev[:, 0]] & hand_m[ev[:, 1]]]: nbr.setdefault(int(a_), []).append(int(b_)); nbr.setdefault(int(b_), []).append(int(a_))
finger_keep = np.zeros(n, bool)
for side, sgn in (("Left", 1), ("Right", -1)):
    region = hand_m & (co[:, 0] * sgn > 0) & (sf > -0.006); core = region & (sf > 0.016)
    label = {}; comps = []
    for v0 in np.nonzero(core)[0]:
        v0 = int(v0)
        if v0 in label: continue
        k = len(comps); label[v0] = k; todo = [v0]; members = []
        while todo:
            v = todo.pop(); members.append(v)
            for u in nbr.get(v, ()):
                if core[u] and u not in label: label[u] = k; todo.append(u)
        comps.append(members)
    reach = sorted(range(len(comps)), key=lambda k: -max(sf[comps[k]]))[:4]; print("  islands past the knuckles:", [(len(c), round(float(max(sf[c])), 3)) for c in comps], "fingers:", reach)
    front = [v for v in label]                                   # grow every island back toward the knuckles; a point joins whichever island reaches it first
    while front:
        nxt = []
        for v in front:
            for u in nbr.get(v, ()):
                if region[u] and u not in label: label[u] = label[v]; nxt.append(u)
        front = nxt
    m = np.zeros(n, bool); m[[v for v, k in label.items() if k in reach]] = True; finger_keep |= m
    b1, b2, b3 = blend(sf), blend(sf - k2), blend(sf - k3)
    new = {side + "Hand": 1 - b1, side + "Fingers1": b1 - b2, side + "Fingers2": b2 - b3, side + "Fingers3": b3}
    rest_m = (co[:, 0] * sgn > 0) & ~m                           # everything else on this side must not move with the fingers
    stray = sum(W[side + f] for f in ("Fingers1", "Fingers2", "Fingers3")) * rest_m
    for name in W:
        if name in new: W[name][m] = new[name][m]
        else: W[name][m] = 0.0
    W[side + "Hand"] = W[side + "Hand"] + stray
    for f in ("Fingers1", "Fingers2", "Fingers3"): W[side + f][rest_m] = 0.0
    idx = [int(i) for i in np.nonzero(m)[0]]; sidx = [int(i) for i in np.nonzero(stray > 0)[0]]
    for g in body.vertex_groups:
        if g.name in new:
            for i in idx: g.add([i], float(new[g.name][i]), 'REPLACE')
            if g.name == side + "Hand":
                for i in sidx: g.add([i], float(W[g.name][i]), 'REPLACE')
            elif sidx: g.remove(sidx)
        else: g.remove(idx)
    print("finger verts", side, len(idx), "moved back to the hand", len(sidx))
# soften the joints: the automatic weights change sharply from one bone to the next, which creases the surface when a joint bends far.
# Averaging each point's weights with its neighbours a few times spreads every bend over a wider band of skin, as on a real body.
all_e = np.empty(len(baked.edges) * 2, dtype=np.int64); baked.edges.foreach_get("vertices", all_e); all_e = all_e.reshape(-1, 2)
deg = np.zeros(n); np.add.at(deg, all_e[:, 0], 1); np.add.at(deg, all_e[:, 1], 1); deg[deg == 0] = 1
for _ in range(8):
    for name in W:
        acc = np.zeros(n); np.add.at(acc, all_e[:, 0], W[name][all_e[:, 1]]); np.add.at(acc, all_e[:, 1], W[name][all_e[:, 0]])
        sm = 0.5 * W[name] + 0.5 * acc / deg; sm[finger_keep] = W[name][finger_keep]; W[name] = sm
tot = sum(W.values()); tot[tot < 1e-6] = 1
for name in W: W[name] = W[name] / tot
for g in body.vertex_groups:
    wv = W[g.name]; g.remove([int(i) for i in np.nonzero(wv < 0.004)[0]])
    for i in np.nonzero(wv >= 0.004)[0]: g.add([int(i)], float(wv[i]), 'REPLACE')
print("weights smoothed")
def w(*names): return sum(W.get(s + k, 0) for k in names for s in ("", "Left", "Right") if (s + k) in W)

# ---------------------------------------------------------------- 6. clothing: the shorts stand a little off the body
nrm = np.empty(n * 3); baked.vertices.foreach_get("normal", nrm); nrm = nrm.reshape(n, 3)
front = np.clip(-nrm[:, 1], 0, 1); back = np.clip(nrm[:, 1], 0, 1); side_n = np.abs(nrm[:, 0])
co2 = co.copy()   # the sculpted anatomy is used exactly as it is: no inflating, widening or pinching
armw = w("Arm", "ForeArm", "Hand", "Fingers1", "Fingers2", "Fingers3")
shorts_v = (Z > HEM * H + 1e-3) & (Z < WAIST * H - 1e-3) & (armw < 0.5)   # the cut edges move too, so hem and waistband stay straight lines
co2 += nrm * (shorts_v * 0.008)[:, None]   # the shorts stand off the body like cloth
baked.vertices.foreach_set("co", co2.ravel()); baked.update()

# ---------------------------------------------------------------- 7. look: a matte ivory mannequin in black shorts
mats = [material("Body", BODY, 0.55), material("Shorts", SHORTS, 0.85)]
for m in mats: baked.materials.append(m)
count = [0, 0]
for p in baked.polygons:
    c = p.center; k = 1 if (HEM * H < c.z < WAIST * H and armw[list(p.vertices)].mean() < 0.5) else 0
    p.material_index = k; count[k] += 1
print("faces: body, shorts", count)
for e in eyes: bpy.data.objects.remove(e, do_unlink=True)   # a mannequin head has no eyes
eyes = []

# ---------------------------------------------------------------- 7b. the new head, made on its own and then joined on
# It is added only now, after the skin weights: the automatic weights work on one sealed body and get confused by a second loose piece.
rx, ry, rz = 0.077, 0.096, 0.112; cz = Ht - rz - 0.020
bm = bmesh.new(); ball = bmesh.ops.create_uvsphere(bm, u_segments=48, v_segments=32, radius=1.0)["verts"]
for v in ball:
    d = v.co.normalized(); lo = max(0.0, -d.z)
    taper = 1.0 - 0.17 * lo ** 1.5 - 0.04 * max(0.0, d.z)                 # narrower toward the chin
    front = 1.0 - 0.05 * max(0.0, -d.y) * (1.0 - abs(d.z))                # a slightly flatter front plane
    v.co = Vector((d.x * rx * taper, hy + d.y * ry * taper * front - 0.030 * lo * lo, cz + d.z * (rz + 0.018 * lo)))
hm = bpy.data.meshes.new("HeadMesh"); bm.to_mesh(hm); bm.free(); hm.materials.append(mats[0])
for p in hm.polygons: p.use_smooth = True
ho = bpy.data.objects.new("HeadPiece", hm); bpy.context.scene.collection.objects.link(ho)
ho.vertex_groups.new(name="Head").add(list(range(len(hm.vertices))), 1.0, 'REPLACE')   # one rigid piece that follows the Head bone
for o in bpy.context.scene.objects: o.select_set(o in (ho, body))
bpy.context.view_layer.objects.active = body; bpy.ops.object.join(); baked = body.data
print("head joined: verts now", len(baked.vertices), "materials", [m.name for m in baked.materials])

# ---------------------------------------------------------------- 8. previews
marks = []
red = material("Joint", (1, 0.1, 0.1, 1))
bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=1, radius=0.014); ball = bpy.data.meshes.new("ball"); bm.to_mesh(ball); bm.free(); ball.materials.append(red)
for b in arm_d.bones:
    o = bpy.data.objects.new("mark", ball); o.location = rig.matrix_world @ b.head_local; bpy.context.scene.collection.objects.link(o); marks.append(o)
render("joints", [body], ghost=True, views=(("front", (0, -1, 0)), ("side", (-1, 0, 0))))
for o in marks: bpy.data.objects.remove(o)
render("final", [body])
rig.pose.bones["LeftArm"].rotation_mode = 'XYZ'; rig.pose.bones["LeftArm"].rotation_euler = (0, 0, math.radians(-50))
rig.pose.bones["RightForeArm"].rotation_mode = 'XYZ'; rig.pose.bones["RightForeArm"].rotation_euler = (math.radians(80), 0, 0)
rig.pose.bones["LeftUpLeg"].rotation_mode = 'XYZ'; rig.pose.bones["LeftUpLeg"].rotation_euler = (math.radians(-70), 0, 0)
rig.pose.bones["LeftLeg"].rotation_mode = 'XYZ'; rig.pose.bones["LeftLeg"].rotation_euler = (math.radians(80), 0, 0)
render("posed", [body], views=(("front", (0, -1, 0)), ("three", (-0.75, -0.65, 0.12))))
for pb in rig.pose.bones: pb.rotation_euler = (0, 0, 0)
# a deep squat with the arms up, to judge how the surface holds its shape at the hips, knees, shoulders and elbows
def bend(name, world_axis, deg):
    pb = rig.pose.bones[name]; pb.rotation_mode = 'QUATERNION'
    local = (rig.matrix_world.to_3x3() @ pb.bone.matrix_local.to_3x3()).inverted() @ Vector(world_axis)
    pb.rotation_quaternion = Quaternion(local.normalized(), math.radians(deg))
for sd in ("Left", "Right"):
    bend(sd + "UpLeg", (-1, 0, 0), 95); bend(sd + "Leg", (1, 0, 0), 105); bend(sd + "Arm", (-1, 0, 0), 55); bend(sd + "ForeArm", (-1, 0, 0), 105)
render("squat", [body], views=(("front", (0, -1, 0)), ("side", (-1, 0, 0)), ("three", (-0.75, -0.65, 0.12)), ("back", (0.4, 1, 0.15))))
for pb in rig.pose.bones: pb.rotation_mode = 'XYZ'; pb.rotation_euler = (0, 0, 0)
# a closed hand, close up: do the fingers fold toward the palm, and does the thumb come across?
def curl(name, world_axis, deg):
    pb = rig.pose.bones[name]; pb.rotation_mode = 'QUATERNION'
    local = (rig.matrix_world.to_3x3() @ pb.bone.matrix_local.to_3x3()).inverted() @ Vector(world_axis)
    pb.rotation_quaternion = Quaternion(local.normalized(), math.radians(deg))
h_ax = Vector(unit0(J["F3"] - J["F1"])); palm = Vector((-1, 0, 0)); palm = (palm - palm.dot(h_ax) * h_ax).normalized(); hinge = h_ax.cross(palm)
for nm, deg in (("LeftFingers1", 45), ("LeftFingers2", 60), ("LeftFingers3", 35)): curl(nm, hinge, deg)
box = []
for p in (Vector(J["Hand"]) + Vector((-0.1, -0.1, 0.04)), Vector(J["FEnd"]) + Vector((0.08, 0.1, -0.04))):
    o = bpy.data.objects.new("corner", ball); o.scale = (0.01,) * 3; o.location = p; bpy.context.scene.collection.objects.link(o); box.append(o)
render("hand", box, views=(("front", (0, -1, 0)), ("inner", (-1, -0.2, 0)), ("back", (1, -0.3, 0))))
for o in box: bpy.data.objects.remove(o)
for pb in rig.pose.bones: pb.rotation_mode = 'XYZ'; pb.rotation_euler = (0, 0, 0)

# ---------------------------------------------------------------- 9. export
for o in bpy.context.scene.objects: o.select_set(o in [body, rig] + eyes)
bpy.context.view_layer.objects.active = rig
glb = os.path.join(OUT, "athlete.glb")
opts = dict(filepath=glb, export_format='GLB', use_selection=True, export_texcoords=False, export_normals=True, export_skins=True, export_animations=False, export_yup=True, export_apply=False, export_materials='EXPORT')
while True:
    try:
        bpy.ops.export_scene.gltf(**opts); break
    except TypeError as e:   # an option this Blender version no longer has: drop it and try again
        bad = [k for k in opts if k in str(e) and k != "filepath"]
        print("export option rejected:", e)
        if not bad: raise
        for k in bad: opts.pop(k)
print("exported", glb, os.path.getsize(glb), "bytes")
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "athlete.blend"), check_existing=False)
