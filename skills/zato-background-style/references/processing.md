# Processing and tuning

The script is local and deterministic. Dependencies: Python 3.10+, NumPy and Pillow (tested with Python 3.12, NumPy from the bundled runtime, Pillow 12.3). No API key, network request, model download, or persistent process is required for conversion.

Before each new skill-driven conversion, ask whether this use should blur logos and wait for the answer unless the current request already states that choice. This question belongs to the agent workflow, not an interactive CLI prompt. A yes answer enables pre-style lettering defocus; a no answer omits blur-mask and blur-regions. Do not carry a prior conversion's selection forward as a permanent default.

## Stages and numeric conventions

1. Decode the original; transpose EXIF orientation; convert an embedded ICC profile to sRGB; retain its oriented alpha channel. Incorrect/unusable ICC profiles fail explicitly. When logo blur is requested, identify lettering on this original and apply selective Gaussian blur now, before the ZATO finish. Retain blurred strokes rather than erasing the signs. Per-letter-size regions are preferred over blurring whole facades.
2. Form sRGB luminance `0.2126 R + 0.7152 G + 0.0722 B`. A small blur blend damps capture noise. Add moderate detail at two radii (1.6 and 9 reference pixels). Normalize the 1.5%/98.5% range; do not apply tonal operations to invisible pixels when estimating source quantiles.
3. Match the source's 101 luminance quantiles towards the selected target. Blend at the profile's tone strength (normally 0.78, exceptional atmospheric profiles 0.65). This is a photographic contrast approximation; it cannot infer which objects the artist masked.
4. Apply a measured, 64-bin luminance-to-RGB lookup table. Most original photos have relatively few exact RGB colors compared with a modern camera photograph. Luminance-dependent hue produces restricted palettes without a single flat color overlay. Retain only 2.5% of source chromatic residual. The default `smooth` photo-adaptation mode fits nondecreasing channel curves (pool-adjacent-violators), smooths with sigma 8 bins, and restores black/highlight endpoints with broad cubic weights. This reduces hue jumps caused by different colored objects sharing a reference luminance. It trades some literal conditional color variation for a usable photo gradient. `--color-curve measured` uses the unmodified empirical LUT. Those raw curves are retained in the profile data for inspection, not silently replaced.
5. Introduce seeded fine and slightly clustered monochrome noise *before* reducing luminance to 9 or 12 representative steps. Noise is gated by `sqrt(4 t (1-t))`, preserving deep ink blacks. Mix 10% continuous tone to soften overly mechanical banding. The procedural texture approximates observed stipple; it is not identified as the artist's original dithering algorithm.
6. Apply restrained screen-like halo around existing small highlights; suppress halos where a large area is already bright. The mild peripheral vignette was applied to tone in stage 3. Project the result into up to 128 colors sampled from the chosen reference-derived photo curve (`adapted` default), without regular-grid dithering. This provides the limited ink gamut without reintroducing abrupt population hue jumps. `--palette-mode reference` instead uses the literal median-cut reference colors and can restore red/yellow bands on a smooth wall even if stage 04 looked good. Preserve source pixels under a supplied protection mask. `--palette-mode continuous` bypasses final gamut projection for soft fog/glass gradients or diagnosis.
7. Save a new RGBA PNG. Requested logo defocus was already applied on the original in step 1; subsequent grain gives its surfaces the same print texture as the rest of the scene. Content layout keeps source dimensions and alpha. The optional 1280×720 game layout places a fine black frame at `[150,93,1130,497)` and a contained or explicitly cropped photograph inside. It does not copy distinctive brushes or graphic overlays from source backgrounds.

Working arrays are sRGB, not scene-linear exposure. All statistics in the profile were measured in the same sRGB convention. This is an aesthetic image operation, not a colorimetric reproduction pipeline. Original image EXIF and GPS are not copied into the exported image; its processing JSON records input and output paths and hashes.

## Parameters

| Argument | Range / default | Intended adjustment |
|---|---|---|
| `--preset` | 12 names; default `cold-cyan` | Select scene-dependent tone/color/texture family |
| `--match-image` | An embedded ordinary background filename | Use individual measured curve and palette; overrides the preset's target |
| `--reference` | User-provided image path | Fit a new reference; mutually exclusive with `--match-image` |
| `--strength` | 0–1; 1 | Final effect blend; 0 retains input RGB and alpha in content layout |
| `--tone-strength` | 0–1; profile default | Influence of target contrast histogram; 0 still retains structure normalization |
| `--grain` | 0–2; 1 | Noise multiplier; 0 disables added noise but retains tonal reduction |
| `--grain-size` | 0.5–4; 1 | Grain feature size relative to 972 reference-panel pixels |
| `--steps` | 4–32; 9 or 12 | Reduced tonal bands; higher values preserve gentle transitions |
| `--palette-mode` | `adapted` default; `reference`; `continuous` | Compact photo-curve gamut, literal measured palette, or continuous LUT colors |
| `--color-curve` | `smooth` default; `measured` | Photo-adapted continuous channel curves vs raw conditional reference colors |
| `--bloom` | 0–0.6; 0.04 or 0.12 | Existing-highlight halo, not new light-source generation |
| `--vignette` | 0–0.5; 0.035 or 0.10 | Peripheral darkening; keep restrained |
| `--defocus` | 0–16 reference pixels; 0 | Deliberate optical blur; not ordinary default |
| `--seed` | Integer; 1701 | Identical content/preset/parameters/seed reproduce pixels |
| `--protect-mask` | Grayscale image | White preserves source, black applies style; gray blends |
| `--blur-mask` | Grayscale image | White selects lettering for blur on the original before grading; match oriented source size |
| `--blur-regions` | JSON, mutually exclusive with blur-mask | oriented_dimensions plus regions containing polygon, radius and optional feather; separate radii for different lettering sizes |
| `--blur-radius` | 0–200 pixels; max(1,width/300) | For blur-mask: start around 15–25% of letter height, keeping visible blurred strokes |
| `--blur-feather` | 0–100 pixels; max(1,width/1500) | Restrained soft boundary; avoid rectangular blur panels |
| `--layout` | `content`, `game-transparent`, `game-white` | Preserve photograph or reproduce game presentation |
| `--fit` | `contain` default; `cover` | Whole image vs explicit crop for game layout |
| `--stages` | Flag | Internal inspection only; write to work/, not deliverables |
| `--images-only` | Flag | Final PNG only; no JSON sidecar; mutually exclusive with stages |

The grain reference width is 972 pixels after excluding border strokes. Detail and grain radii scale with photograph width. For a large portrait, visible grain may differ from a panoramic reference: inspect native pixels and adjust `--grain-size`. Rendering a game layout downsamples the photograph after grading and can attenuate grain; compare the final frame as well as its full-resolution content output. A future exact perceptual match may require fitting texture at the final panel resolution.

## Troubleshooting

- **Everything is blue/yellow:** This may be the intended dominant ink palette; if a target has mixed hues, use its individual profile. These profiles do not label semantic objects or preserve natural skin hues automatically.
- **Unreadable important areas:** Lower tone strength; use a protection mask for a face, sign or doorway. Reducing final strength also retains some of the original color. A broad brightening changes the style's black masses, so prefer local preservation when appropriate.
- **Photo looks like a generic old-film filter:** Confirm that the LUT and tonal reduction stages actually ran. The important operations are tonal massing and luminance-conditioned color, not noise alone.
- **Overly regular bands:** Increase steps to 12–16 or increase grain moderately. Avoid excessive global blur which removes the architectural detail.
- **A red/yellow or purple/pink stripe across a smooth wall:** This is a hue-curve jump, not necessarily luminance posterization. Defaults `--color-curve smooth --palette-mode adapted` address empirical LUT reversals and palette snapping together. Do not keep raising steps or reducing grain if the stripe is already visible in stage 04 (before grain). If stage 05 is good but stage 06 is not, check whether literal `reference` palette projection was requested. Try a more suitable individual reference or continuous palette mode, then review the actual result.
- **False dark sky / changed scenery:** No semantic sky mask is inferred. If the user wants a night sky or winter landscape, first perform the requested content edit through an available image tool and inspect it.
- **A completely flat source:** The script leaves it unchanged and warns rather than hallucinating texture. Fully transparent input, animated input, mismatched masks and unusable references fail explicitly.
- **Ambiguous output filename:** The script creates a numbered suffix; it never overwrites an existing output or the source. Report the actual emitted paths.

## Validation meaning

Each saved PNG is decoded and checked against the intended pixels. Source hash is checked before and after, and content-layout alpha is compared exactly. These checks establish file correctness and preservation invariants; they do not certify aesthetic similarity. `result_content_metrics` excludes framing; compare it with the chosen reference while acknowledging scene-dependent differences. Never tune every photograph to the same mean brightness merely to minimize a histogram difference.

The user's current delivery contract is two finished images (cold-cyan and amber), with no other attachments or final-response text. CLI diagnostics may be captured internally in work/. Optional logo blur does not detect brands automatically: inspect and select lettering on the original per photo, preserve traffic directions and unrelated detail, and check that the lettering remains as fuzzy strokes rather than disappearing into a flat bar. Do not use mosaic or opaque covers. Inspect both the softened original and final grade. Style strength and protection masks affect grading of the prepared original; explicitly requested logo blur happens beforehand. Stage 01 shows the prepared photograph, including any requested pre-style defocus.
