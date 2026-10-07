---
name: zato-background-style
description: Convert user photographs into the measured photographic background style of Z.A.T.O. I Love the World and Everything In It, with ink-black shadows, restricted tonal palettes, stochastic print grain, and optional transparent game framing. Use when the user requests ZATO-style photo processing or matching these ZATO background references.
---

# ZATO background style

Turn the supplied photograph into a scene-appropriate approximation of the user's ZATO background collection. This skill uses measured reference profiles and an offline image-processing script. It does not train a neural model or recover the original artist's exact editing history.

## Ask about logos at each use

The user explicitly requests: **“在每次使用的时候进行提问是否模糊 logo。”** At the start of every new photo-conversion request using this skill, ask **“这次是否模糊图片中的 logo？”** with two choices: **“模糊 logo，保留模糊字形”** and **“不模糊，保留原标识”**. Use the available user-question tool. This is a processing preference, not an extra permission request. Wait for the answer before preparing branding masks or generating the two final variants; while waiting, source inspection is fine. Do not treat a preselected option, elapsed time or a previous conversion's choice as the answer for this use.

If the current request already explicitly specifies whether to blur logos, the choice is answered and need not be asked again. Ask once for a batch unless the user requests different choices per image. Refinements within the same answered conversion retain its choice; the next new use asks again. This initial question is allowed by the two-image delivery preference below; the completed photo-conversion response still contains only the two finished images.

If the answer is yes, follow the original-photo defocus workflow below. If no, omit all branding-blur options and keep the logos through ordinary style processing.

## User's delivery preference

The user explicitly requests: **“以后输出仅仅输出这两张图片，其他都不需要输出。”** For each photograph, deliver exactly two finished PNGs: the cold-cyan version first and the warm amber version second. A later explicit request may change their styles or number.

Keep the deliverable folder limited to those two images. The final response consists only of two embedded images in that order: no explanatory prose, separate download links, comparisons, thumbnails, stage sheets, parameter JSON, validation reports or skill archives. Keep any necessary inspection crops, masks, stage images and records in the workspace's `work/` directory. Use `--images-only` for the final outputs. Continue to inspect and verify the images internally.

## Inspect and choose

View the source image before processing. Note subject, illumination, readable details, orientation, and transparency. Preserve objects and perspective. Refer to [style-guide.md](references/style-guide.md) for scene selection and evidence; view [style-board.jpg](references/style-board.jpg) when visual comparison helps.

- The corpus contains 123 RGBA images, all 1280×720. Most use a roughly 980×404 photograph within a transparent canvas. Do not interpret hidden RGB/transparent margins as a white sky or a black background.
- Twelve scene palettes are embedded. Ordinary winter/day architecture often fits `cold-cyan`; warm rooms `amber`; oppressive stairwells `olive`, `teal` or `rose`; street lights `blue-night` or `violet`. `pale-fog`, `frost-glow`, and `sunset-red` cover their distinct exceptions.
- If the user specifies a background filename, prefer `--match-image filename.png`, which uses that image's embedded full-resolution color/tonal statistics. There are 100 ordinary image profiles. The 23 utility/effect frames were analyzed but excluded from normal photo calibration.
- If an external reference is supplied, view it and use `--reference path`. Never fit a solid black/white frame as a style. The script excludes common transparent framing when fitting a reference.
- If no palette is specified, produce cold-cyan and amber variants in accordance with the user's delivery preference, tuning their contrast and grain to the source scene. The script's `auto` option is only a brightness heuristic; it cannot identify indoor scenes or recognize objects.

## Execute

For requested photo conversions, run `scripts/zato_style.py` with Python, Pillow and NumPy. Use the workspace dependency runtime if available; otherwise a Python runtime with those two packages. Treat the actual installed skill folder as `SKILL_DIR`; paths below are examples, not hardcoded installation requirements.

```powershell
& $taskPython "$SKILL_DIR\scripts\zato_style.py" "D:\photos\scene.jpg" `
  --output-dir "D:\photos\zato-output" --preset cold-cyan --images-only

& $taskPython "$SKILL_DIR\scripts\zato_style.py" "D:\photos\scene.jpg" `
  --output-dir "D:\photos\zato-output" --preset amber --images-only
```

Use `--list-presets` or `--list-reference-images` to discover available choices. A file, several files, or a directory may be passed; add `--recursive` only when nested inputs are wanted. Output names are collision-safe and sources are retained.

Default `--layout content` preserves EXIF-oriented dimensions and the source alpha plane. When the user explicitly requests game framing, use `--layout game-transparent` or `game-white` for the two requested outputs. Do not add a third framed variant. `--fit contain` preserves the entire image. Use `cover` only when cropping is requested or accepted; portrait photos normally need the content layout. A game layout resizes the photograph and changes its canvas intentionally.

## Optional logo blur

After the logo-choice question is answered yes (or the current request explicitly asks for blur), inspect the original at sufficient resolution and mark the visible brand symbols, wordmarks and identifying shop names. Keep unrelated architecture, vehicles, road arrows and ordinary scene detail intact. This is local optical blur, not object removal or replacement.

The user specifically corrected the operation order and appearance: **return to the original photograph, identify logos there, optically blur the original lettering first, and only then apply the ZATO finish. Text must remain visibly present as blurred strokes, while its wording becomes difficult to read.** Do not use mosaic, pixel blocks, solid fills, opaque bars, inpainting or broad blur that erases the whole sign. Keep signboard edges and surrounding texture.

Choose tight polygons around the actual lettering, allowing a small soft margin. Different letter sizes need different blur radii: start around 15–25% of the letter height and inspect; stop when wording loses clarity but blurred letter shapes remain. For mixed sizes, use `--blur-regions path` with JSON containing `oriented_dimensions: [width,height]` and `regions: [{polygon: [[x,y],...], radius: pixels, feather: pixels}]`. Coordinates refer to the original EXIF-oriented photograph. Keep the JSON and inspection crops in `work/`. For uniform lettering sizes, `--blur-mask path` accepts a grayscale mask: white selects lettering, black preserves source, gray partially blends. Blur is performed on the original sRGB image before structure, tone and grain processing; both variants share the same softened original. Inspect the pre-styled lettering and final results at native resolution. The script does not automatically detect logos. Apply this option when requested, rather than treating it as a permanent request to blur every future photo.

## Refine and verify

Read [processing.md](references/processing.md) when tuning parameters, dealing with masks, or diagnosing artifacts. If stage inspection is needed, run `--stages` to an internal `work/` directory; deliver only the two selected final PNGs.

Inspect the final image at normal viewing size and a native-pixel crop. Review:

- Dark masses should look intentional, while doors, faces, text and important silhouettes remain understandable.
- Grain should appear as irregular ink-like stipple with dark areas staying clean. Avoid a uniform translucent noise layer or regular dot-grid pattern.
- Color should be mostly governed by luminance and the selected reference palette. Preserve the distinction between an amber room, a blue winter scene and a red effect.
- Halo should surround existing small light sources. Do not add lamps, snow, stars, buildings or hand-painted sky masks simply to make a scene resemble the game's subject matter.
- Watch halos on rooflines, severe banding in smooth sky, clipping on skin, and accidental subject cropping. Check the per-image JSON warnings and alpha/dimension validation.

Adjust only parameters implicated by the observed mismatch. Lower `--tone-strength` if structural information disappears; reduce `--grain` or increase `--steps` if stipple becomes distracting; reduce `--bloom` for bright skies. A hue stripe already visible in stage 04 is a color-curve issue, not added grain: retain the defaults `--color-curve smooth --palette-mode adapted` and consider a better-matched individual reference. If stage 05 is good but stage 06 introduces bands, check literal reference-palette snapping; use adapted or continuous mode. For selective detail preservation, supply `--protect-mask`: white preserves original pixels and black applies the effect. Masks must match the oriented source dimensions. See the processing reference for numeric ranges and scale conventions.

Changes to season, architecture, object content, or day-to-night lighting are a separate creative edit; use an available image-editing tool if the user asks for those changes, then apply this finish. Do not represent a global color grade as a complete relighting operation.

Return only the two final embedded images according to the delivery preference above. Keep parameters and validation internal unless the user explicitly asks for them. Do not claim that statistical similarity proves an exact visual match.
