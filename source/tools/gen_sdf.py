"""Generate TMP-compatible SDF glyph tables + Alpha8 atlases from TTF fonts.

Usage: python gen_sdf.py <font_path> <point_size> <padding> <atlas_size> <out_prefix>
Writes <out_prefix>.json (glyph list + face info) and <out_prefix>.png (top-down atlas preview)
and <out_prefix>.a8 (raw Alpha8 bytes, bottom-up rows, as Unity stores them).
"""
import json, math, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import distance_transform_edt
from fontTools.ttLib import TTFont

U = 8  # supersampling factor

VN = ("ăâđêôơưĂÂĐÊÔƠƯ"
      "áàảãạắằẳẵặấầẩẫậéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ"
      "ÁÀẢÃẠẮẰẲẴẶẤẦẨẪẬÉÈẺẼẸẾỀỂỄỆÍÌỈĨỊÓÒỎÕỌỐỒỔỖỘỚỜỞỠỢÚÙỦŨỤỨỪỬỮỰÝỲỶỸỴ")
EXTRA = "‘’“”…–—•€™"


def charset():
    cs = [chr(c) for c in range(32, 127)] + [chr(c) for c in range(0xA1, 0x100)]
    for c in VN + EXTRA:
        if c not in cs:
            cs.append(c)
    return cs


def build(font_path, pt, pad, atlas, font_index=0, target_cap_ratio=None):
    size_hi = pt * U
    font = ImageFont.truetype(font_path, size_hi, index=font_index)
    tt = TTFont(font_path, fontNumber=font_index, lazy=True)
    cmap = tt.getBestCmap()
    upem = tt["head"].unitsPerEm
    post = tt["post"]
    gs = pad + 1
    glyphs, bitmaps = [], []
    for ch in charset():
        if ord(ch) not in cmap:
            continue
        adv = font.getlength(ch) / U
        if ch == " " or ch == " ":
            glyphs.append(dict(id=ord(ch), w=0, h=0, xo=0.0, yo=0.0, adv=adv))
            bitmaps.append(None)
            continue
        x0, y0, x1, y1 = font.getbbox(ch, anchor="ls")
        if x1 <= x0 or y1 <= y0:
            glyphs.append(dict(id=ord(ch), w=0, h=0, xo=0.0, yo=0.0, adv=adv))
            bitmaps.append(None)
            continue
        X0, Y0 = math.floor(x0 / U) * U, math.floor(y0 / U) * U
        X1, Y1 = math.ceil(x1 / U) * U, math.ceil(y1 / U) * U
        m = pad * U
        W, H = X1 - X0 + 2 * m, Y1 - Y0 + 2 * m
        img = Image.new("L", (W, H), 0)
        ImageDraw.Draw(img).text((m - X0, m - Y0), ch, font=font, fill=255, anchor="ls")
        mask = np.asarray(img) > 127
        inside = distance_transform_edt(mask)
        outside = distance_transform_edt(~mask)
        d = (inside - outside) / U  # in low-res pixels
        v = np.clip(0.5 + d / (2 * gs), 0, 1)
        lw, lh = W // U, H // U
        v = v.reshape(lh, U, lw, U).mean(axis=(1, 3))
        bitmaps.append((v * 255 + 0.5).astype(np.uint8))
        glyphs.append(dict(id=ord(ch), w=(X1 - X0) // U, h=(Y1 - Y0) // U,
                           xo=X0 / U, yo=-Y0 / U, adv=adv))

    # shelf packing (top-down coordinates)
    order = sorted(range(len(glyphs)), key=lambda i: -(bitmaps[i].shape[0] if bitmaps[i] is not None else 0))
    A = np.zeros((atlas, atlas), np.uint8)
    cx = cy = 1
    shelf = 0
    for i in order:
        bm = bitmaps[i]
        g = glyphs[i]
        if bm is None:
            g["x"], g["y"] = 0.0, 0.0
            continue
        h, w = bm.shape
        if cx + w + 1 > atlas:
            cx = 1
            cy += shelf + 1
            shelf = 0
        if cy + h + 1 > atlas:
            raise SystemExit(f"atlas overflow for {font_path} at pt {pt}")
        A[cy:cy + h, cx:cx + w] = np.maximum(A[cy:cy + h, cx:cx + w], bm)
        g["x"], g["y"] = float(cx + pad), float(cy + pad)
        cx += w + 1
        shelf = max(shelf, h)

    asc, desc = font.getmetrics()
    asc, desc = asc / U, desc / U
    hb = font.getbbox("H", anchor="ls")
    cap = -hb[1] / U
    space_adv = font.getlength(" ") / U
    ul = post.underlinePosition / upem * pt
    ult = max(post.underlineThickness / upem * pt, 1.0)
    point_field = float(pt)
    if target_cap_ratio:
        f = target_cap_ratio / (cap / pt)
        f = min(max(f, 0.75), 1.1)
        point_field = pt / f
    face = dict(PointSize=point_field, Scale=1.0, CharacterCount=len(glyphs),
                LineHeight=asc + desc, Baseline=0.0, Ascender=asc, CapHeight=cap,
                Descender=-desc, CenterLine=0.0, SuperscriptOffset=asc,
                SubscriptOffset=ul, SubSize=0.5, Underline=ul, UnderlineThickness=ult,
                TabWidth=space_adv * 10, Padding=float(pad),
                AtlasWidth=float(atlas), AtlasHeight=float(atlas))
    used = cy + shelf + 1
    return glyphs, face, A, used


if __name__ == "__main__":
    fp, pt, pad, atlas, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
    idx = int(sys.argv[6]) if len(sys.argv) > 6 else 0
    tcr = float(sys.argv[7]) if len(sys.argv) > 7 else None
    glyphs, face, A, used = build(fp, pt, pad, atlas, idx, tcr)
    json.dump(dict(glyphs=glyphs, face=face), open(out + ".json", "w"))
    Image.fromarray(A).save(out + ".png")
    open(out + ".a8", "wb").write(np.flipud(A).tobytes())
    print(f"{out}: {len(glyphs)} glyphs, atlas rows used {used}/{atlas}, PointSize field {face['PointSize']:.2f}")
