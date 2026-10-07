# Visual evidence and scene selection

## Corpus and evidence boundary

The user's directory `ZATO_全部图片/images/bgs` contains 123 RGBA PNGs at 1280×720. All were inspected in seven contact sheets and measured individually. 113 have substantial transparent margins; their photographic panel lies approximately at x=150–1130, y=93–497. Calibration samples the inside x=154–1126, y=95–493, avoiding frame strokes and irregular brush overflow. The remaining ten opaque images include six window cutouts, black/white utility frames and two full-canvas special graphics.

100 images inform ordinary-photo profiles. The other 23 are still documented in `corpus-analysis.json` but excluded from palette/contrast fitting: five defocus frames, three icy flashes, five stairwell pulses, six window cutouts, two solid utility frames, a glitch frame and a full-canvas illustration. Color variants of the same scene are averaged within a palette family before scene-level profiles receive equal weight. A long sequence of stairwell variants must not dominate the room-photo style.

Measured in the photographic crop, ordinary images have median 38.14% of pixels below sRGB luminance 0.10; the middle half ranges from 19.84% to 49.65%. Median pixels above 0.90: 8.51%. Median count of exact RGB colors: 561. These are collection summaries, not desired constants for every subject. A snowy fog landscape has far fewer dark pixels than a cinema or red alarm scene.

The data establishes appearance, not authorship technique. There is no original ungraded photo, layered editing file, filter history or known training set. Exact editor names, historical operation order, camera settings and original grain parameters cannot be recovered from these final PNGs. The script's recipe values are documented engineering hypotheses.

## Core appearance

**Photographic structure remains visible.** Perspective, architectural joints, handwriting, reflections and clutter survive. This is largely photography reduced to graphic masses, rather than uniformly redrawn anime architecture. Empty snowy streets, institutional buildings, kitchens, stairwells, glass blocks and industrial fans are recurring subjects; they are content motifs and should not be inserted into an unrelated user photo.

**Black is structural.** Continuous dark regions swallow some low-frequency detail. Narrow high-contrast edges and bright shapes carry readability. A general desaturation-and-grain filter leaves too much camera-like tonal continuity. At the same time, do not turn every scene into a binary threshold: fog, sky, glass, sunsets and optical blur require intermediate values.

**Hue depends strongly on tone.** Many backgrounds use black → a few colored midtones → pale colored/white highlights. Highlights are not necessarily neutral white: icy cyan, lilac, greenish ivory and warm cream matter. Modern multicolored objects are largely subordinated to the selected palette. Some cold scenes mix cyan and deeper blue; some warm scenes mix yellow and reddish brown. A single solid tint misses this relationship.

**Texture is fine and irregular.** Native-pixel crops show highly contrasted point-like stipple. Dots concentrate in transitions and midtones; clean blacks and pale masses persist. They are not a regular newspaper dot grid, a watercolor paper overlay, scanlines across every image, or a spatially uniform white-noise veil. Quantization, noise and subsequent color mapping plausibly interact. Native texture measurements also include actual scene detail, so they cannot isolate a unique noise process.

**Local light and masks matter.** Night variants retain pools of light around pre-existing lamps and windows while substantially darkening larger areas. Some skies, borders and illumination look edited separately. A luminance LUT alone does not reconstruct those spatial masks. Strong requests to change time/season require a separately reviewed semantic edit.

**Presentation is separate.** Fine black frame, wide transparent margins and occasional overflow brushes or circular graphic marks belong to the composition layer. Preserve content aspect ratio by default; reproduce the canvas in an additional game-framed variant when wanted. Do not include transparent outer pixels in style measurements or copy decorative marks automatically.

## Palette families

| Preset | Ordinary images / scene groups | Typical references | Distinct treatment |
|---|---:|---|---|
| `cold-cyan` | 17 / 17 | street, roofs, dvor, sch_close | Cold winter cyan and blue; pale snow; strong ink edges |
| `blue-night` | 7 / 7 | school_night, roofsnight, streetnightedit | Blue-black shadows and selected bright lamps/windows |
| `violet` | 9 / 8 | street2night, dvory, barracks day | Lavender/purple midtones, pale violet snow and dark masses |
| `amber` | 19 / 16 | asyakitchen, asyaroomday, cafe2, cinema | Yellow cream and brown/black; cozy yet oppressive indoor light |
| `olive` | 12 / 7 | podyezdmarina, library, sch_window | Greenish ivory and olive; muted, sickly institutional atmosphere |
| `rose` | 20 / 13 | niihall, stairs, marinakitchen | Dark rose and dusty pink; warmer than violet |
| `teal` | 3 / 2 | podyezdira, vents | Sparse cyan-green against heavy black |
| `alarm-red` | 3 / 3 | vents_red, carfix_red, bodyshop | Strong red and near-white against especially heavy black |
| `monochrome` | 2 / 2 | cafe4, skygray | Grayscale or nearly neutral ink treatment |
| `pale-fog` | 2 / 2 | tundra, polarnight | Deliberately low contrast, pale teal/pink haze; little black |
| `frost-glow` | 5 / 2 | inej, inej2–4, sunrise1 | Bright fine structure and soft cold glow; not ordinary hard architecture |
| `sunset-red` | 1 / 1 | sunrise2 | Black landscape silhouette, narrow warm/red sunset light |

Sparse families have less statistical support. Use individual reference matching when a particular look is intended; do not imply that a one-scene sunset preset represents a learned universal sunset model.

## Choosing an individual target

Use `--match-image` for the exact background's measured palette/tonal distribution. This option stores numbers, not the background's objects, and can work after the original game folder moves. Available filenames are discovered by `--list-reference-images`. A match preserves source geometry; it does not transplant room details or scenery.

Choose by illumination and structure as well as hue. A photograph with a large blank sky may resemble `street.png` in color but need different tone strength than an indoor shelf. Start with a matching family or individual target, inspect, then tune. A faithful transformation is not achieved by forcing identical color histograms across unrelated content.

## Reading detailed measurements

`corpus-analysis.json` contains dimensions, transparency/crop, SHA-256, role, scene family, RGB mean/deviation, luminance quantiles, saturation, dark/highlight fractions, edges, multiscale texture, exact color frequencies, entropy and frequency-band energy. The separately delivered CSV and JSON contain the same measurements. These describe observable images; none is a direct measurement of an artist's blur radius or film ISO.

`profiles.json` contains 12 scene-balanced recipes; `individual-profiles.json` contains 100 ordinary-background profiles. Both include a 64-bin RGB LUT, 101 target luminance quantiles, a reference-derived compact RGB palette, observed texture/contrast statistics and estimated processing coefficients. Small preview images here are for visual selection only; the numeric profiles were fitted from the original panel pixels, not resized thumbnails.
