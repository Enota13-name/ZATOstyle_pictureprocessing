#!/usr/bin/env python3
"""Offline, reference-fitted ZATO photo grading. Requires numpy and Pillow."""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import math
from pathlib import Path
import sys
import time
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps, ImageCms

SKILL = Path(__file__).resolve().parents[1]
LUMA = np.array([.2126, .7152, .0722], dtype=np.float32)
EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tif', '.tiff'}

def as_image(a):
    return Image.fromarray(np.rint(np.clip(a, 0, 1)*255).astype(np.uint8))

def blur(a, radius):
    if radius <= 0:
        return a.copy()
    return np.asarray(as_image(a).filter(ImageFilter.GaussianBlur(radius)), dtype=np.float32)/255

def load_photo(path):
    with Image.open(path) as opened:
        if getattr(opened, 'n_frames', 1) > 1:
            raise ValueError('Animated input needs an explicit frame-export workflow; no frames silently discarded.')
        im = ImageOps.exif_transpose(opened)
        alpha = np.asarray(im.convert('RGBA').getchannel('A')).copy()
        icc = im.info.get('icc_profile')
        rgb = im.convert('RGB')
        color_note = 'Input treated as sRGB'
        if icc:
            try:
                icc_input=im if im.mode in ('RGB','CMYK','LAB','L') else rgb
                rgb = ImageCms.profileToProfile(icc_input, ImageCms.ImageCmsProfile(io.BytesIO(icc)), ImageCms.createProfile('sRGB'), outputMode='RGB')
                color_note = 'Embedded ICC converted to sRGB'
            except (ValueError, OSError, ImageCms.PyCMSError) as exc:
                raise ValueError(f'Cannot safely convert embedded ICC profile: {exc}') from exc
        return rgb, alpha, color_note

def photo_metrics(a, alpha=None):
    h, w = a.shape[:2]
    thumb = as_image(a)
    thumb.thumbnail((972, 540), Image.Resampling.LANCZOS)
    x = np.asarray(thumb, dtype=np.float32)/255
    mask = np.ones(x.shape[:2], dtype=bool)
    if alpha is not None:
        mask = np.asarray(Image.fromarray(alpha).resize(thumb.size, Image.Resampling.NEAREST)) > 127
    if not mask.any():
        return {'empty_visible_region': True}
    y = x@LUMA
    residual = y-blur(y, 1.2)
    vals = y[mask]
    return {'mean_rgb': np.round(x[mask].mean(0), 5).tolist(), 'luma_quantiles': np.round(np.quantile(vals, [.05,.25,.5,.75,.95]), 5).tolist(), 'shadow_fraction_010': round(float((vals<.1).mean()), 5), 'highlight_fraction_090': round(float((vals>.9).mean()), 5), 'fine_texture_rms_at_972px': round(float(residual[mask].std()), 5)}

def custom_reference(path, template):
    rgb, alpha, _ = load_photo(path)
    if rgb.size == (1280,720) and (alpha==0).mean()>.2:
        box = (154,95,1126,493)
    elif (alpha==0).mean()>.2:
        box = Image.fromarray(alpha).getbbox()
        if box is None:
            raise ValueError('Reference is fully transparent.')
    else:
        box = (0,0,*rgb.size)
    arr = np.asarray(rgb.crop(box),dtype=np.float32)/255
    y = arr@LUMA
    if float(y.std()) < .015:
        raise ValueError('Reference has insufficient tonal variation; choose a photograph, not a solid utility frame.')
    bins = np.clip((y*63).astype(int),0,63)
    lut = np.full((64,3), np.nan)
    counts = np.bincount(bins.ravel(), minlength=64)
    for c in range(3):
        sums = np.bincount(bins.ravel(),weights=arr[:,:,c].ravel(),minlength=64)
        np.divide(sums,counts,out=lut[:,c],where=counts>20)
        valid = np.isfinite(lut[:,c])
        lut[:,c] = np.interp(np.arange(64),np.where(valid)[0],lut[valid,c])
    metrics = photo_metrics(arr)
    if metrics['shadow_fraction_010']>.08:
        lut[0]=0
    fitted = json.loads(json.dumps(template))
    fitted['rgb_lut']=lut.tolist()
    fitted['luma_quantiles']=np.quantile(y,np.linspace(0,1,101)).tolist()
    fitted['recipe']['grain_amplitude']=float(np.clip(metrics['fine_texture_rms_at_972px']*.80,.035,.12))
    pal=rgb.crop(box).quantize(colors=128,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE)
    palette=np.asarray(pal.getpalette(),dtype=np.uint8).reshape(-1,3)
    fitted['palette_rgb']=palette[np.unique(np.asarray(pal))].tolist()
    fitted['recipe']['palette_colors']=len(fitted['palette_rgb'])
    fitted['custom_reference']={'path':str(Path(path).resolve()),'sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest(),'crop':box,'metrics':metrics}
    return fitted

def quantile_map(base, target_q, valid):
    source_q = np.quantile(base[valid], np.linspace(0,1,len(target_q)))
    unique, first, counts = np.unique(source_q, return_index=True, return_counts=True)
    target = np.array([np.mean(target_q[i:i+c]) for i,c in zip(first,counts)])
    return np.interp(base, unique, target).astype(np.float32)

def structured_noise(rng, shape, scale):
    h,w=shape
    small_h=max(1,int(math.ceil(h/scale)));small_w=max(1,int(math.ceil(w/scale)))
    noise=rng.standard_normal((small_h,small_w)).astype(np.float32)
    # Resample a bounded field so grain size follows the reference panel scale.
    bounded=np.clip(noise/6+.5,0,1)
    field=np.asarray(as_image(bounded).resize((w,h),Image.Resampling.NEAREST),dtype=np.float32)/255
    return (field-.5)*6

def photo_adapted_lut(lut):
    """Monotone channel fitting prevents population hue jumps on smooth photos.

    The raw reference LUT remains available through color_curve='measured'.
    Pool-adjacent-violators fits are followed by broad 1D Gaussian smoothing.
    """
    result=lut.copy()
    for c in range(3):
        pools=[]
        for value in lut[:,c]:
            pools.append([float(value),1])
            while len(pools)>1 and pools[-2][0]>pools[-1][0]:
                b=pools.pop();a=pools.pop();n=a[1]+b[1]
                pools.append([(a[0]*a[1]+b[0]*b[1])/n,n])
        fitted=np.array([value for value,n in pools for _ in range(n)],dtype=np.float32)
        axis=np.arange(-24,25,dtype=np.float32);kernel=np.exp(-axis**2/(2*8.**2));kernel/=kernel.sum()
        smoothed=np.convolve(np.pad(fitted,(24,24),mode='edge'),kernel,mode='valid')
        # Preserve ink black and highlight color without an endpoint jump.
        t=np.linspace(0,1,len(lut))
        result[:,c]=smoothed+(lut[0,c]-smoothed[0])*(1-t)**3+(lut[-1,c]-smoothed[-1])*t**3
    return np.clip(result,0,1)

def apply_style(rgb, alpha, profile, *, strength=1., grain=1., seed=1701,
                tone_strength=None, bloom=None, vignette=None, defocus=0.,
                protect=None, grain_size=1., steps=None, palette_mode='adapted', color_curve='smooth', collect_stages=False):
    original=np.asarray(rgb,dtype=np.float32)/255
    y=original@LUMA
    valid=alpha>127
    if not valid.any():
        raise ValueError('Input has no visible pixels.')
    recipe=profile['recipe']
    params={'strength':strength,'grain':grain,'seed':seed,'tone_strength':recipe['tone_strength'] if tone_strength is None else tone_strength,'bloom':recipe['bloom'] if bloom is None else bloom,'vignette':recipe['vignette'] if vignette is None else vignette,'defocus':defocus,'grain_size':grain_size,'tonal_steps':recipe['tonal_steps'] if steps is None else steps,'detail_gain':recipe['detail_gain'],'grain_amplitude':recipe['grain_amplitude'],'color_residual':recipe['color_residual']}
    stages={'01_original':original.copy()} if collect_stages else {}
    warnings=[]
    params['palette_mode']=palette_mode
    params['reference_palette_colors']=recipe.get('palette_colors')
    params['palette_colors']=None
    params['color_curve']=color_curve
    if float(y[valid].std())<.008:
        warnings.append('Almost uniform source: retained original, no synthetic texture injected.')
        return original,stages,params,warnings
    scale=max(.4,rgb.width/972)
    denoised=blur(y,.45*scale)
    base=.82*y+.18*denoised
    base+=recipe['detail_gain']*(base-blur(base,1.6*scale))
    base+=recipe['detail_gain']*.45*(base-blur(base,9*scale))
    lo,hi=np.quantile(base[valid],[.015,.985])
    if hi-lo>.02:
        base=np.clip((base-lo)/(hi-lo),0,1)
    else:
        base=np.clip(base,0,1)
    matched=quantile_map(base,np.asarray(profile['luma_quantiles']),valid)
    tone=np.clip((1-params['tone_strength'])*base+params['tone_strength']*matched,0,1)
    h,w=tone.shape
    yy,xx=np.mgrid[:h,:w]
    radius=((xx-(w-1)/2)/(max(w,1)/2))**2+((yy-(h-1)/2)/(max(h,1)/2))**2
    # Only a mild peripheral falloff; dramatic sky erasure needs a supplied mask.
    tone*=1-params['vignette']*np.clip((radius-.3)/1.7,0,1)
    if defocus:
        tone=blur(tone,defocus*scale)
    if collect_stages:
        stages['02_structure']=np.repeat(base[:,:,None],3,axis=2)
        stages['03_tone']=np.repeat(tone[:,:,None],3,axis=2)
    lut=np.asarray(profile['rgb_lut'],dtype=np.float32)
    if color_curve=='smooth':
        lut=photo_adapted_lut(lut)
    knots=np.linspace(0,1,len(lut))
    def grade(t):
        mapped=np.stack([np.interp(t,knots,lut[:,c]) for c in range(3)],axis=-1)
        residual=original-y[:,:,None]
        return np.clip(mapped+recipe['color_residual']*residual,0,1).astype(np.float32)
    if collect_stages:
        stages['04_palette_without_grain']=grade(tone)
    rng=np.random.default_rng(seed)
    fine=structured_noise(rng,(h,w),scale*grain_size)
    clustered=blur(np.clip(structured_noise(rng,(h,w),scale*grain_size*2.2)/6+.5,0,1),.6*scale)
    clustered=(clustered-.5)*6
    # Stochastic grain precedes tonal reduction; clean black masses survive.
    envelope=np.sqrt(np.clip(4*tone*(1-tone),0,1))
    ink_field=.86*fine+.30*clustered
    perturbed=np.clip(tone+params['grain_amplitude']*grain*envelope*ink_field,0,1)
    depth=params['tonal_steps']-1
    grainy=np.rint(perturbed*depth)/depth
    # A low mixture of continuous tone prevents banding on fog, glass and skin.
    grainy=.90*grainy+.10*perturbed
    grainy[tone<.025]=0
    result=grade(grainy)
    if collect_stages:
        stages['05_ink_grain']=result.copy()
    # Halation around small existing highlights; no invented lamps or snow.
    large_average=blur(tone,18*scale)
    light=np.clip((tone-.80)/.20,0,1)*np.clip((.82-large_average)/.25,0,1)
    halo=blur(light,7*scale)+.45*blur(light,22*scale)
    result=1-(1-result)*(1-np.clip(params['bloom']*halo,0,.5)[:,:,None])
    if palette_mode!='continuous' and profile.get('palette_rgb'):
        if palette_mode=='adapted':
            # A raw population palette can snap a smooth wall back to unrelated
            # red/yellow object colors. Quantize the chosen photo curve instead.
            palette=np.rint(np.clip(np.stack([np.interp(np.linspace(0,1,128),knots,lut[:,c]) for c in range(3)],axis=-1),0,1)*255).astype(np.uint8).tolist()
        else:
            palette=profile['palette_rgb']
        params['palette_colors']=len({tuple(color) for color in palette})
        pal=Image.new('P',(1,1))
        padded=palette+[palette[0]]*(256-len(palette))
        pal.putpalette([v for color in padded for v in color])
        result=np.asarray(as_image(result).quantize(palette=pal,dither=Image.Dither.NONE).convert('RGB'),dtype=np.float32)/255
    amount=np.full((h,w),strength,dtype=np.float32)
    if protect is not None:
        amount*=1-protect
    # Hidden pixels are preserved; alpha itself is never graded.
    amount[alpha==0]=0
    result=np.clip(original*(1-amount[:,:,None])+result*amount[:,:,None],0,1)
    if collect_stages:
        stages['06_final_content']=result.copy()
    final_metrics=photo_metrics(result,alpha)
    if final_metrics['shadow_fraction_010']>.72:
        warnings.append('Over 72% of visible pixels are dark: review readability and lower tone strength if needed.')
    return result,stages,params,warnings

def game_layout(im, layout, fit):
    if layout=='content':
        return im,None
    canvas=Image.new('RGBA',(1280,720),(255,255,255,255 if layout=='game-white' else 0))
    if fit=='cover':
        panel=ImageOps.fit(im,(978,402),method=Image.Resampling.LANCZOS)
    else:
        panel=ImageOps.contain(im,(978,402),method=Image.Resampling.LANCZOS)
    x=151+(978-panel.width)//2;y=94+(402-panel.height)//2
    canvas.alpha_composite(panel,(x,y))
    ImageDraw.Draw(canvas).rectangle((150,93,1129,496),outline=(0,0,0,255),width=1)
    return canvas,{'canvas':[1280,720],'panel_frame':[150,93,1130,497],'fit':fit,'photo_box':[x,y,x+panel.width,y+panel.height],'cropping':fit=='cover','outer_alpha':255 if layout=='game-white' else 0}

def blur_selected_regions(result,alpha,mask_path,radius=None,feather=None):
    """Optically soften selected lettering on the original, before grading."""
    h,w=result.shape[:2]
    with Image.open(mask_path) as opened:
        mask=ImageOps.exif_transpose(opened).convert('L')
    if mask.size!=(w,h):
        raise ValueError(f'Blur mask dimensions {mask.size} do not match oriented source {(w,h)}.')
    radius=max(1.,w/300) if radius is None else radius
    feather=max(1.,w/1500) if feather is None else feather
    if feather:mask=mask.filter(ImageFilter.GaussianBlur(feather))
    amount=np.asarray(mask,dtype=np.float32)/255
    amount[alpha==0]=0
    softened=np.asarray(as_image(result).filter(ImageFilter.GaussianBlur(radius)),dtype=np.float32)/255
    mixed=result*(1-amount[:,:,None])+softened*amount[:,:,None]
    return mixed,{'mask':str(Path(mask_path).resolve()),'mask_sha256':hashlib.sha256(Path(mask_path).read_bytes()).hexdigest(),'radius_pixels':radius,'feather_pixels':feather,'selected_fraction':float((amount>0).mean()),'position_in_pipeline':'Original sRGB photograph before structure, tone, grain and framing; alpha unchanged.'}

def blur_original_regions(rgb,alpha,regions_path):
    """Per-wordmark Gaussian blur; different lettering sizes need different radii."""
    data=json.loads(Path(regions_path).read_text(encoding='utf-8'))
    if data.get('oriented_dimensions')!=list(rgb.size):
        raise ValueError('Logo region coordinates do not match the oriented photo dimensions.')
    validated=[]
    for region in data['regions']:
        polygon=region['polygon'];radius=float(region['radius']);feather=float(region.get('feather',2))
        if len(polygon)<3 or not 0<radius<=200 or not 0<=feather<=100:
            raise ValueError('Invalid logo polygon, radius or feather.')
        points=[]
        for point in polygon:
            if len(point)!=2 or not all(isinstance(v,(int,float)) and math.isfinite(v) for v in point):
                raise ValueError('Logo coordinates must be finite numeric pairs.')
            x,y=point
            if not 0<=x<=rgb.width or not 0<=y<=rgb.height:raise ValueError('Logo polygon lies outside the photograph.')
            points.append((x,y))
        validated.append((region,points,radius,feather))
    prepared=rgb.copy()
    for region,points,radius,feather in validated:
        padding=math.ceil(3*(radius+feather))+2
        box=(max(0,int(min(p[0] for p in points))-padding),max(0,int(min(p[1] for p in points))-padding),min(rgb.width,int(math.ceil(max(p[0] for p in points)))+padding),min(rgb.height,int(math.ceil(max(p[1] for p in points)))+padding))
        crop=rgb.crop(box)
        mask=Image.new('L',crop.size,0)
        ImageDraw.Draw(mask).polygon([(x-box[0],y-box[1]) for x,y in points],fill=255)
        if feather:mask=mask.filter(ImageFilter.GaussianBlur(feather))
        selection=np.asarray(mask).copy()
        selection[alpha[box[1]:box[3],box[0]:box[2]]==0]=0
        prepared.paste(crop.filter(ImageFilter.GaussianBlur(radius)),box[:2],Image.fromarray(selection))
    return prepared,{'regions':str(Path(regions_path).resolve()),'regions_sha256':hashlib.sha256(Path(regions_path).read_bytes()).hexdigest(),'region_count':len(validated),'position_in_pipeline':'Original sRGB photograph before structure, tone, grain and framing; alpha unchanged.','method':'Gaussian optical defocus, selected per lettering height; lettering remains as blurred traces.'}

def contact_sheet(stages,path):
    sheet=Image.new('RGB',(1440,900),'#eae8e4');draw=ImageDraw.Draw(sheet)
    for i,(name,a) in enumerate(stages.items()):
        if i>=6:break
        x=i%3*480;y=i//3*450
        im=as_image(a);im.thumbnail((464,402),Image.Resampling.LANCZOS)
        sheet.paste(im,(x+(480-im.width)//2,y+(402-im.height)//2))
        draw.text((x+12,y+420),name,fill='#252525')
    sheet.save(path,quality=92)

def available_output(out, stem):
    for n in range(1,10000):
        name=stem if n==1 else f'{stem}_{n:02d}'
        # Companion files reserve a name too, even after a previous partial run.
        if not any((out/(name+suffix)).exists() for suffix in ['.png','.json','_stages.jpg']):
            return out/(name+'.png')
    raise ValueError('Too many output collisions.')

def run_file(path,args,profiles,out):
    source_hash=hashlib.sha256(path.read_bytes()).hexdigest()
    rgb,alpha,color_note=load_photo(path)
    chosen=args.preset
    if chosen=='auto':
        x=np.asarray(rgb,dtype=np.float32)/255
        mean=float((x@LUMA)[alpha>127].mean()) if (alpha>127).any() else 0
        chosen='blue-night' if mean<.28 else 'cold-cyan'
    profile=profiles[chosen]
    if args.match_image:
        individual=json.loads((SKILL/'references/individual-profiles.json').read_text(encoding='utf-8'))
        key=Path(args.match_image).name
        if key not in individual:
            raise ValueError(f'No ordinary-background profile for {key}. Use --list-reference-images; effect frames are deliberately excluded.')
        profile=individual[key]
        chosen=profile['source_reference']['preset']
    if args.reference:
        profile=custom_reference(args.reference,profile)
    protect=None
    if args.protect_mask:
        mask=ImageOps.exif_transpose(Image.open(args.protect_mask)).convert('L')
        if mask.size!=rgb.size:
            raise ValueError(f'Protection mask dimensions {mask.size} do not match oriented source {rgb.size}.')
        protect=np.asarray(mask,dtype=np.float32)/255
    start=time.time()
    source_metrics=photo_metrics(np.asarray(rgb,dtype=np.float32)/255,alpha)
    local_blur=None
    if getattr(args,'blur_mask',None):
        softened,local_blur=blur_selected_regions(np.asarray(rgb,dtype=np.float32)/255,alpha,args.blur_mask,getattr(args,'blur_radius',None),getattr(args,'blur_feather',None))
        rgb=as_image(softened)
    elif getattr(args,'blur_regions',None):
        rgb,local_blur=blur_original_regions(rgb,alpha,args.blur_regions)
    result,stages,params,warnings=apply_style(rgb,alpha,profile,strength=args.strength,grain=args.grain,seed=args.seed,tone_strength=args.tone_strength,bloom=args.bloom,vignette=args.vignette,defocus=args.defocus,protect=protect,grain_size=args.grain_size,steps=args.steps,palette_mode=args.palette_mode,color_curve=args.color_curve,collect_stages=args.stages)
    rgba=np.dstack((np.rint(result*255).astype(np.uint8),alpha))
    painted=Image.fromarray(rgba)
    painted,layout_info=game_layout(painted,args.layout,args.fit)
    dest=available_output(out,path.stem+'_zato_'+chosen)
    if dest.resolve()==path.resolve():
        raise ValueError('Refusing to overwrite source.')
    painted.save(dest,'PNG')
    with Image.open(dest) as verify:
        verify.load()
        if verify.size!=painted.size or verify.convert('RGBA').tobytes()!=painted.tobytes():
            raise ValueError('PNG round-trip verification failed.')
        if args.layout=='content' and not np.array_equal(np.asarray(verify.getchannel('A')),alpha):
            raise ValueError('Source alpha preservation failed.')
    if hashlib.sha256(path.read_bytes()).hexdigest()!=source_hash:
        raise ValueError('Source changed during processing.')
    report={'input':str(path.resolve()),'source_sha256':source_hash,'output':str(dest.resolve()),'output_sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'preset':chosen,'preset_label':profile['label'],'input_oriented_dimensions':list(rgb.size),'output_dimensions':list(painted.size),'color_management':color_note,'parameters':params,'reference':profile.get('custom_reference') or profile.get('source_reference'),'layout':args.layout,'layout_details':layout_info,'local_blur':local_blur,'source_metrics':source_metrics,'result_content_metrics':photo_metrics(result,alpha),'target_observed_statistics':profile['observed'],'warnings':warnings,'validation':'Source hash unchanged; PNG round-trip checked; source alpha checked for content layout. No geometric remapping in content layout.','elapsed_seconds':round(time.time()-start,2),'method':'Measured color/tonal profiles and deterministic procedural texture; no neural model training, no scene content generation.'}
    if args.stages:
        stage_dir=out/(dest.stem+'_stages');stage_dir.mkdir()
        for name,a in stages.items():as_image(a).save(stage_dir/(name+'.png'))
        sheet_path=out/(dest.stem+'_stages.jpg');contact_sheet(stages,sheet_path)
        report['stages_directory']=str(stage_dir.resolve());report['stage_comparison']=str(sheet_path.resolve())
    if not getattr(args,'images_only',False):
        dest.with_suffix('.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True),flush=True)
    return report

def bounded(lo,hi,integer=False):
    def value(s):
        n=int(s) if integer else float(s)
        if not lo<=n<=hi:
            raise argparse.ArgumentTypeError(f'Expected {lo}..{hi}')
        return n
    return value

def main():
    data=json.loads((SKILL/'references/profiles.json').read_text(encoding='utf-8'))
    profiles=data['profiles']
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('inputs',nargs='*',type=Path)
    p.add_argument('--output-dir',type=Path)
    p.add_argument('--preset',choices=['auto',*profiles],default='cold-cyan')
    p.add_argument('--list-presets',action='store_true')
    references=p.add_mutually_exclusive_group()
    references.add_argument('--reference',type=Path)
    references.add_argument('--match-image',help='Embedded original background filename, e.g. asyakitchen.png.')
    p.add_argument('--list-reference-images',action='store_true')
    p.add_argument('--strength',type=bounded(0,1),default=1.)
    p.add_argument('--grain',type=bounded(0,2),default=1.)
    p.add_argument('--grain-size',type=bounded(.5,4),default=1.)
    p.add_argument('--tone-strength',type=bounded(0,1))
    p.add_argument('--bloom',type=bounded(0,.6))
    p.add_argument('--vignette',type=bounded(0,.5))
    p.add_argument('--defocus',type=bounded(0,16),default=0.)
    p.add_argument('--steps',type=bounded(4,32,True))
    p.add_argument('--palette-mode',choices=['adapted','reference','continuous'],default='adapted')
    p.add_argument('--color-curve',choices=['smooth','measured'],default='smooth')
    p.add_argument('--seed',type=int,default=1701)
    p.add_argument('--layout',choices=['content','game-transparent','game-white'],default='content')
    p.add_argument('--fit',choices=['contain','cover'],default='contain')
    p.add_argument('--protect-mask',type=Path,help='White preserves source; black applies the style.')
    branding=p.add_mutually_exclusive_group()
    branding.add_argument('--blur-mask',type=Path,help='White selects lettering for Gaussian blur on the original, before grading.')
    branding.add_argument('--blur-regions',type=Path,help='JSON with oriented_dimensions and regions (polygon, radius, feather); blur each wordmark before grading.')
    p.add_argument('--blur-radius',type=bounded(0,200),help='Gaussian blur radius in oriented source pixels; default max(1,width/300).')
    p.add_argument('--blur-feather',type=bounded(0,100),help='Blur-mask feather in pixels; default max(1,width/1500).')
    p.add_argument('--images-only',action='store_true',help='Save final PNG only; suppress JSON and stage deliverables.')
    p.add_argument('--stages',action='store_true')
    p.add_argument('--recursive',action='store_true')
    args=p.parse_args()
    if args.images_only and args.stages:p.error('--images-only and --stages are mutually exclusive; inspect stages in work/ instead.')
    if args.list_presets:
        print(json.dumps({k:{'label':v['label'],'reference_count':v['reference_count'],'independent_scene_count':v['independent_scene_count']} for k,v in profiles.items()},ensure_ascii=True));return
    if args.list_reference_images:
        individual=json.loads((SKILL/'references/individual-profiles.json').read_text(encoding='utf-8'))
        print(json.dumps({k:v['source_reference']['preset'] for k,v in individual.items()},ensure_ascii=True));return
    if not args.inputs or args.output_dir is None:p.error('Provide source file(s)/directory and --output-dir.')
    out=args.output_dir.resolve();out.mkdir(parents=True,exist_ok=True)
    inputs=[]
    for path in args.inputs:
        if path.is_dir():
            candidates=path.rglob('*') if args.recursive else path.iterdir()
            inputs.extend(sorted(q for q in candidates if q.is_file() and q.suffix.lower() in EXTENSIONS and not q.resolve().is_relative_to(out)))
        elif path.is_file():inputs.append(path)
        else:p.error(f'Input does not exist: {path}')
    inputs=list(dict.fromkeys(q.resolve() for q in inputs))
    if not inputs:p.error('No supported photos found.')
    errors=[]
    for path in inputs:
        try:run_file(path,args,profiles,out)
        except Exception as exc:
            errors.append({'input':str(path),'error':str(exc)})
            print(json.dumps(errors[-1],ensure_ascii=True),file=sys.stderr,flush=True)
    if errors:raise SystemExit(1)

if __name__=='__main__':main()
