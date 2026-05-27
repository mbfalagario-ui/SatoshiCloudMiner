"""Verify and repair image MIME types — Build #16/17 hotfix.

Gemini Nano Banana sometimes returns JPEG bytes even when we ask for PNG;
EAS expo-doctor catches this and fails the build. This script:
 1. Inspects every image we ship
 2. If the file extension says .png but the magic bytes are JPEG, RE-encodes
    the pixel data as actual PNG (lossless conversion via Pillow)
 3. Re-runs and reports the after state.
"""
from PIL import Image
import os

PATHS = [
    '/app/frontend/assets/images/icon.png',
    '/app/frontend/assets/images/adaptive-icon.png',
    '/app/frontend/assets/images/favicon.png',
    '/app/frontend/assets/images/splash-icon.png',
    '/app/store/marketing/icon-1024.png',
    '/app/store/marketing/banner-hero.png',
    '/app/store/marketing/banner-feature-mine.png',
    '/app/store/marketing/banner-feature-yield.png',
    '/app/store/marketing/banner-feature-support.png',
    '/app/store/marketing/banner-cta.png',
]


def magic(path):
    with open(path, 'rb') as f:
        head = f.read(8)
    if head.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'PNG'
    if head.startswith(b'\xff\xd8\xff'):
        return 'JPG'
    return f'OTHER({head[:4].hex()})'


def repair_to_png(path):
    """Decode whatever's in the file (JPG, PNG, etc.) and write back as
    real RGBA PNG. Idempotent."""
    img = Image.open(path)
    # convert to RGBA for transparency support; for icons that's correct
    img = img.convert('RGBA')
    img.save(path, format='PNG', optimize=True)
    return img.size


print('=' * 78)
print('BEFORE')
print('=' * 78)
needs_fix = []
for p in PATHS:
    if not os.path.exists(p):
        print(f'  (missing) {p}')
        continue
    m = magic(p)
    sz = os.path.getsize(p)
    print(f'  {m:8s}  {sz/1024:7.1f}KB  {p}')
    if m != 'PNG' and p.endswith('.png'):
        needs_fix.append(p)

if not needs_fix:
    print('\nAll files already valid PNG — no work to do.')
else:
    print(f'\n{len(needs_fix)} file(s) need re-encoding from JPG → PNG:')
    for p in needs_fix:
        print(f'  → fixing {p} ...')
        sz_before = os.path.getsize(p)
        size = repair_to_png(p)
        sz_after = os.path.getsize(p)
        print(f'      size={size}  {sz_before/1024:.1f}KB → {sz_after/1024:.1f}KB')

print('\n' + '=' * 78)
print('AFTER')
print('=' * 78)
for p in PATHS:
    if not os.path.exists(p):
        continue
    m = magic(p)
    sz = os.path.getsize(p)
    print(f'  {m:8s}  {sz/1024:7.1f}KB  {p}')

print('\nDone.')
