# Build the Health OS athlete.
# Source body: Blender Studio "Human Base Meshes" v1.4.1, realistic male body (CC0, https://www.blender.org/download/demo-files/).
# Steps: import -> bake sculpt detail -> thin the mesh for phones -> find joints from the body's shape -> build a skeleton
#        -> automatic skin weights -> athletic shaping -> materials (skin, shorts, hair, eyes) -> previews -> export GLB.
# Run it with start-builder.bat (Blender without a window) or through run.py in Blender's Text Editor. Everything printed ends up in log.txt.
import bpy, bmesh, os, glob, math
import numpy as np
from mathutils import Vector, Matrix

BLEND = glob.glob(os.path.join(HERE, "assets", "**", "human_base_meshes_bundle.blend"), recursive=True)[0]
OUT = HERE
SKIN, SHORTS, HAIR = (0.56, 0.34, 0.23, 1), (0.05, 0.13, 0.42, 1), (0.03, 0.022, 0.018, 1)   # linear colour values
HEM, WAIST = 0.365, 0.585   # shorts: bottom edge and waistband, as a share of body height


def reset():   # clear the scene without reloading the file (reloading would close the script that is running)
    if bpy.context.object and bpy.context.object.mode != 'OBJECT': bpy.ops.object.mode_set(mode='OBJECT')
    for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)
    for c in list(bpy.data.collections): bpy.data.collections.remove(c)
    for blk in (bpy.data.meshes, bpy.data.armatures, bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        for d in list(blk):
            if d.users == 0: blk.remove(d)


def material(name, rgba, rough=0.6):
    m = bpy.data.materials.new(name); m.use_nodes = True; m.diffuse_color = rgba
    b = m.node_tree.nodes.get("Principled BSDF")
    if b: b.inputs["Base Color"].default_value = rgba; b.inputs["Roughness"].default_value = rough
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
dec = body.modifiers.new("Decimate", 'DECIMATE'); dec.ratio = 0.16 if mr.levels == 2 else 0.6
dg = bpy.context.evaluated_depsgraph_get()
baked = bpy.data.meshes.new_from_object(body.evaluated_get(dg), depsgraph=dg)
body.modifiers.clear(); body.data = baked; body.name = "Athlete"; baked.name = "Athlete"
Hraw = max(v.co.z for v in baked.vertices)
bm = bmesh.new(); bm.from_mesh(baked)
for frac in (HEM, WAIST):   # cut the surface along the shorts' edges so the colour boundary is a clean line
    bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(0, 0, frac * Hraw), plane_no=(0, 0, 1), dist=0.0005)
bm.to_mesh(baked); bm.free(); baked.validate(); baked.update()
for p in baked.polygons: p.use_smooth = True
print("mesh after bake: verts", len(baked.vertices), "polys", len(baked.polygons), "tris", sum(len(p.vertices) - 2 for p in baked.polygons))

# ---------------------------------------------------------------- 3. joints from the body's shape
n = len(baked.vertices); co = np.empty(n * 3); baked.vertices.foreach_get("co", co); co = co.reshape(n, 3)
X, Y, Z = co[:, 0], co[:, 1], co[:, 2]; H = Z.max(); print("height", round(H, 3))
def cen(mask, fallback=None):
    return co[mask].mean(axis=0) if mask.sum() > 3 else np.array(fallback)
def torso_y(z): return cen((abs(X) < 0.10) & (abs(Z - z) < 0.02), (0, 0, z))[1]
crotch = Z[abs(X) < 0.008].min(); print("crotch z", round(crotch, 3))
J = {}
hipc = cen((X > 0.02) & (X < 0.22) & (Z > crotch - 0.06) & (Z < crotch - 0.02))
J["UpLeg"] = np.array([hipc[0] * 0.92, hipc[1] + 0.005, crotch + 0.085])
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
print("arm length", round(L, 3), "tip", np.round(tip, 3))
spine = {"Hips": 0.555, "Spine": 0.61, "Spine1": 0.67, "Spine2": 0.735, "Neck": 0.858, "Head": 0.912}
C = {k: np.array([0, torso_y(f * H) + (0.02 if k in ("Neck", "Head") else 0.012), f * H]) for k, f in spine.items()}
C["HeadEnd"] = np.array([0, C["Head"][1], H])
for k, v in list(J.items()) + list(C.items()): print("  joint", k, np.round(v, 3))

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
def w(*names): return sum(W.get(s + k, 0) for k in names for s in ("", "Left", "Right") if (s + k) in W)

# ---------------------------------------------------------------- 6. athletic shaping: push muscle groups out along the surface normal, draw the waist in
nrm = np.empty(n * 3); baked.vertices.foreach_get("normal", nrm); nrm = nrm.reshape(n, 3)
front = np.clip(-nrm[:, 1], 0, 1); back = np.clip(nrm[:, 1], 0, 1); side_n = np.abs(nrm[:, 0])
amt = (w("Arm") * 0.007 + w("ForeArm") * 0.004 + w("Shoulder") * 0.008 + w("Spine2") * (0.007 * front + 0.006 * back + 0.004 * side_n)
       + w("Spine1") * 0.004 * side_n * (Z > 1.10) - w("Spine") * 0.005 * side_n + w("UpLeg") * 0.005 + w("Leg") * 0.006 * back + w("Neck") * 0.005 * (side_n + back))
co2 = co + nrm * amt[:, None]
wide = np.clip((Z - 1.24) / 0.10, 0, 1) * np.clip((1.47 - Z) / 0.05, 0, 1)   # a touch more shoulder width
co2[:, 0] *= 1 + 0.035 * wide
cloth = ((Z > HEM * H + 0.001) & (Z < WAIST * H - 0.001) & (w("Arm", "ForeArm", "Hand") < 0.3)) * 0.004   # shorts stand a few millimetres off the skin
co2 += nrm * cloth[:, None]
baked.vertices.foreach_set("co", co2.ravel()); baked.update()

# ---------------------------------------------------------------- 7. materials
skin, shorts, hair = material("Skin", SKIN), material("Shorts", SHORTS, 0.85), material("Hair", HAIR, 0.9)
for m in (skin, shorts, hair): baked.materials.append(m)
hem, waist = HEM * H, WAIST * H
armw = w("Arm", "ForeArm", "Hand")
for p in baked.polygons:
    c = p.center; vi = list(p.vertices)
    if hem < c.z < waist and armw[vi].mean() < 0.3: p.material_index = 1
    elif c.z > 0.93 * H:
        line = 0.984 * H - 0.066 * H * min(1, max(0, (c.y - C["Head"][1] + 0.085) / 0.12))   # hairline: high at the forehead, low at the back of the head
        if c.z > line: p.material_index = 2
print("faces: skin", sum(p.material_index == 0 for p in baked.polygons), "shorts", sum(p.material_index == 1 for p in baked.polygons), "hair", sum(p.material_index == 2 for p in baked.polygons))
white, iris = material("EyeWhite", (0.92, 0.92, 0.9, 1), 0.3), material("Iris", (0.12, 0.07, 0.04, 1), 0.3)
for e in eyes:
    e.data = e.data.copy(); e.data.materials.clear(); e.data.materials.append(white); e.data.materials.append(iris)
    mw = e.matrix_world.copy(); cy = mw.translation.y
    for p in e.data.polygons: p.material_index = 1 if (mw @ p.center).y < cy - 0.0105 else 0
    e.parent = rig; e.matrix_world = mw; g = e.vertex_groups.new(name="Head"); g.add(range(len(e.data.vertices)), 1.0, 'REPLACE')
    md = e.modifiers.new("Armature", 'ARMATURE'); md.object = rig

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
