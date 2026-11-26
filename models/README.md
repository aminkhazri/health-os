# Models

`body.glb` is the anatomical figure on the app's Body tab: the skeleton and the muscles of the whole body, grouped into the app's muscle keys.

- **Source:** BodyParts3D 4.0, © The Database Center for Life Science, licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
  (https://dbarchive.biosciencedbc.jp/en/bodyparts3d/), taken in the packed form published by the open-source
  [human-atlas](https://github.com/ashemag/human-atlas) viewer.
- **Changes made here:** parts selected and regrouped by muscle, simplified to keep the file small, fibre data added.
  BodyParts3D has no latissimus dorsi or rectus abdominis, so those two (and the lumbar aponeurosis) are generated from the skin surface.
  They are approximations, not sculpted anatomy.
- **Rebuild:** `python3 tools/anatomy/build_body.py <human-atlas>/public/models models/body.glb`

This is a training aid, not a medical reference.
