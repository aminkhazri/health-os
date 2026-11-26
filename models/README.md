# Models

`body.glb` is the anatomical figure on the app's Body tab: the skeleton and the muscles of the whole body, grouped into the app's muscle keys.

## Licence and credit

`body.glb` is licensed **[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)**. This is a different licence from the app's code:
it applies to this model file only.

- **Z-Anatomy, the libre 3D atlas of anatomy**, CC BY-SA 4.0 (https://github.com/Z-Anatomy/Models-of-human-anatomy)
- which is derived from **BodyParts3D**, © The Database Center for Life Science, CC BY-SA 2.1 Japan
  (https://dbarchive.biosciencedbc.jp/en/bodyparts3d/)

If you reuse or change the model, keep this credit and share your version under the same licence.

## Changes made here

- muscles, a few tendon sheets and the skeleton kept; fascia layers, bursae, organs, vessels and nerves left out
- parts regrouped by muscle; very dense parts simplified; coarse muscles subdivided and smoothed
- the tendon sheet of the external oblique is cut away where it covers the rectus abdominis, so the abs show
- the head, hands and feet are replaced by plain smooth shapes (no skull, face, fingers bones or toes)
- numbers baked into every point for the app's shader: a fibre number, an occlusion shade, how tendon-like the point is (muscles fade to pale tendon at their ends) and a small per-muscle tint
- Z-Anatomy's "ascending" and "descending" trapezius labels are swapped in its file; the parts are sorted by height here

## Rebuild

Blender is not needed: `extract_zanatomy.py` reads the `.blend` file directly.

    # unzip Z-Anatomy.zip from the Z-Anatomy repository to get Z-Anatomy/Startup.blend
    python3 tools/anatomy/extract_zanatomy.py Z-Anatomy/Startup.blend z.npz
    python3 tools/anatomy/build_body.py z.npz models/body.glb

This is a training aid, not a medical reference.
