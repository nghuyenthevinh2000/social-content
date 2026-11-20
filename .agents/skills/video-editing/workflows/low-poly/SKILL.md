---
name: low-poly
description: Makes a PS1/N64-era low-poly 3D animation for a reel, in the style of "low poly shorts". Chunky low-resolution pixels, wobbly vertices, dithering, flat warm lighting and small yellow captions with a thin black outline. The built-in scene is a train platform: a dog sits and waits, a train brakes in and pulls away, and he is still there in the snow. Use when the user runs /low-poly or asks for a low-poly, PS1-style, retro 3D or "low poly shorts" animation.
---

# /low-poly

```
┌──────────────────────┐
│  [ SHIBUYA ]         │  pixel-font station sign (your names)
│  <EBISU  HARAJUKU>   │
│        ▟▙            │  a cream low-poly dog, sitting
│ ▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬   │  yellow tactile strip
│  for almost 10 years │  small yellow caption, thin black outline
│ ═╪══╪══╪══╪══╪══╪═   │  the train passes here; snow after it
└──────────────────────┘
```

## First use
This skill's folder is the "Base directory" Claude Code shows when it loads it.
```bash
SKILL_DIR="<base directory of this skill>"
KIT=$(python3 -c 'import os,sys;print(os.path.realpath(os.path.join(sys.argv[1],"..","..","kit")))' "$SKILL_DIR")
[ -s "$KIT/vendor/gsap.min.js" ] && [ -d "$KIT/node_modules/three" ] || bash "$KIT/setup.sh"
```
Needs ffmpeg and Node.

## Steps
1. **Words.** Two captions: the setup while the dog waits, and the turn when the train has gone ("he waited every day" / "for almost 10 years"). Lowercase, no full stops, like the channel's captions. Check the facts of the story.
2. **Spec.** Write `<name>.lowpoly.json` (below).
3. **Build.** Run `python3 "$SKILL_DIR/build.py" <spec.json>`. It takes about 1.5 minutes (WebGL in headless Chrome). Add `--snap 3.0` for a quick PNG.
4. **Check** the sheet: the dog and the captions sit inside the red frame.
5. **Hand over** the mp4 path.

## Spec
```json
{"lines": ["he waited every day", "for almost 10 years"], "sign": "SHIBUYA", "prev": "EBISU", "next": "HARAJUKU", "snow": true}
```
- **`lines`**: line one shows from 0.3 s, line two from 2.6 s, just before the train clears.
- **`sign`**, **`prev`**, **`next`**: the station sign and the stations either side. A tiny pixel font, so letters, digits, spaces, dots and dashes only. Up to 10 characters print large, up to 20 small.
- **`snow`**: after the train passes, petals turn to falling snow and a little snow sits on the dog (time has passed). `false` keeps spring.
- **`hold`** (optional): extra seconds at the end. **`out`** (optional): the output path.

Timeline: the dog waits (0–1.2 s), the train hides him (1.2–2.67 s), he is revealed (2.67 s), and he turns his head down the platform (3.45–3.95 s). For a reel that shows only part of the clip, start around 2.75 s to open on the dog.

## Make another scene
Copy `template.html` next to the spec, set `"template": "my-scene.html"`, and change the models. Keep what makes the style:
- Render the scene at 360x640 and show it 3x with nearest-neighbour scaling.
- Snap vertices a little in the shader and dither the colours.
- Draw textures in code at 16–64 px with nearest filtering, and keep models to a few boxes, cones and cylinders.
- Use a wide lens close to the subject, and a small yellow caption about two thirds of the way down.

## Taste
- True, slightly sad or strange stories suit it: animals, history, odd facts.
- Named after the style of "low poly shorts" videos; not affiliated with any channel.
