# Models

`athlete.glb` is the 3D figure the app's exercise demos animate.

- **Source body:** Blender Studio "Human Base Meshes" v1.4.1, realistic male body. License: CC0 (public domain). https://www.blender.org/download/demo-files/
- **Built by:** `tools/blender/build_body.py`, run in Blender 5.3. It bakes sculpt detail, thins the mesh to about 55,000 triangles, replaces the head with a blank egg shape, finds the joints from the body's shape, cuts clean clothing edges into the surface, builds a 22-bone skeleton, computes skin weights, adds muscle, and assigns four matte materials: body, T-shirt, shorts and trainers.
- **Bone names** match what `src/Figure3D.html` steers: Hips, Spine, Spine1, Spine2, Neck, Head, and Left/Right Shoulder, Arm, ForeArm, Hand, UpLeg, Leg, Foot, ToeBase.

To rebuild: put the unzipped base-mesh bundle under `assets/` next to the scripts, set `HERE` in `run.py` to that folder, and run `blender -b -P run.py`.
