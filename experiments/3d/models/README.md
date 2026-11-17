# Model

`athlete.glb` is the figure the app's demos use, with the finished animation clips saved inside it.

- **Figure:** the Mesh2Motion human mannequin (https://mesh2motion.org), released under CC0 (public domain). It is a drawing-mannequin style
  figure with separate segments at each joint, so it keeps its shape however far a joint bends.
- **Push-up clip:** from the same Mesh2Motion library (CC0), used as authored.
- **Goblet squat clip:** built by `tools/motion/animate.py`.

Rebuild it with:

    python3 tools/motion/mannequin.py human-addon-animations.glb step1.glb Pushup=Push-up
    python3 tools/motion/animate.py step1.glb models/athlete.glb

`tools/blender/` holds the earlier approach (a sculpted body rigged in Blender). It is kept for reference and is no longer used by the app.
