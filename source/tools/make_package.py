"""Build the data folder for the public Vietnamese installer.

Reads pristine game files from DNFTM_backup_original (dev machine only) and writes
vietnamese/installer/data/:
  text.json      section -> key -> [english_source, vietnamese]   (only translated keys)
  credits.json   header line map for enCredits -> koCredits
  fonts.json     per asset file / path_id: expected font name, glyph table, face info, atlas id
  atlas_N.bin    zlib-compressed Alpha8 atlases (bottom-up rows, as Unity stores them)
  LICENSES/      OFL licence texts of the bundled fonts
No original game file or game text other than the English source strings needed for
matching is shipped.
"""
import json, os, shutil, sys, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_vi  # noqa: E402
from build_vi import BACKUP, GAME, ROOT, CREDITS_MAP, merge_translations  # noqa: E402
import UnityPy  # noqa: E402
import numpy as np  # noqa: E402
from gen_sdf import build as gen_build  # noqa: E402

FONTS = os.path.join(ROOT, "vietnamese", "fonts_ofl")
DATA = os.path.join(ROOT, "vietnamese", "installer", "data")

REG = "bevietnampro_BeVietnamPro-Regular.ttf"
BOLD = "bevietnampro_BeVietnamPro-Bold.ttf"
HAND = "patrickhand_PatrickHand-Regular.ttf"
SERIF = "NotoSerif-VF.ttf"
OFL_PLAN = {
    "sharedassets2.assets": {
        253: (BOLD, 48), 254: (REG, 48), 255: (BOLD, 48), 256: (HAND, 61), 257: (BOLD, 48),
        258: (BOLD, 48), 259: (REG, 48), 260: (SERIF, 48), 261: (REG, 48), 262: (REG, 48),
    },
    "sharedassets3.assets": {
        11764: (BOLD, 48), 11765: (BOLD, 48), 11766: (REG, 48), 11767: (REG, 48),
        11768: (REG, 48), 11769: (REG, 48), 11770: (REG, 48), 11771: (REG, 48),
    },
}


def make_text():
    env = UnityPy.load(os.path.join(BACKUP, "resources.assets"))
    objs = {o.read().m_Name: o for o in env.objects if o.type.name == "TextAsset"}
    en = json.loads(objs["en"].read().m_Script.lstrip("﻿"))
    vi, count, problems = merge_translations(en)
    if problems:
        raise SystemExit("\n".join(problems))
    out = {}
    for sec, items in en.items():
        for k, v in items.items():
            if isinstance(v, str) and vi[sec][k] != v:
                out.setdefault(sec, {})[k] = [v, vi[sec][k]]
    n = sum(len(x) for x in out.values())
    json.dump(out, open(os.path.join(DATA, "text.json"), "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    json.dump(CREDITS_MAP, open(os.path.join(DATA, "credits.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"text: {n} translated strings")


def make_fonts():
    from UnityPy.helpers.TypeTreeGenerator import TypeTreeGenerator
    gen = TypeTreeGenerator("5.6.1f1")
    gen.load_local_dll_folder(os.path.join(GAME, "Managed"))
    node = gen.get_nodes_up("Assembly-CSharp-firstpass", "TMPro.TMP_FontAsset")
    meta, cache = {}, {}
    for fn, plan in OFL_PLAN.items():
        env = UnityPy.load(os.path.join(BACKUP, fn))
        objs = {o.path_id: o for o in env.objects}
        meta[fn] = {}
        for pid, (ttf, pt) in plan.items():
            tr = objs[pid].read_typetree(node)
            fi = tr["m_fontInfo"]
            pad, atlas = int(fi["Padding"]), int(fi["AtlasWidth"])
            target = fi["CapHeight"] / fi["PointSize"] if fi["CapHeight"] > 0 else None
            key = (ttf, pt, pad, atlas, round(target or 0, 4))
            if key not in cache:
                glyphs, face, A, used = gen_build(os.path.join(FONTS, ttf), pt, pad, atlas, 0, target)
                aid = f"atlas_{len(cache)}.bin"
                open(os.path.join(DATA, aid), "wb").write(zlib.compress(np.flipud(A).tobytes(), 9))
                cache[key] = dict(glyphs=glyphs, face=face, atlas_file=aid)
                print(f"  {aid}: {ttf} pt{pt} pad{pad} ({len(glyphs)} glyphs, rows {used}/{atlas})")
            tex = objs[tr["atlas"]["m_PathID"]].read()
            meta[fn][str(pid)] = dict(
                name=tr["m_Name"], font_name=os.path.splitext(ttf)[0].split("_")[-1],
                atlas_size=atlas, padding=pad, atlas_path_id=tr["atlas"]["m_PathID"],
                atlas_name=tex.m_Name, **cache[key])
    json.dump(meta, open(os.path.join(DATA, "fonts.json"), "w", encoding="utf-8"), separators=(",", ":"))
    print(f"fonts: {sum(len(v) for v in meta.values())} font assets, {len(cache)} atlases")


if __name__ == "__main__":
    if os.path.isdir(DATA):
        shutil.rmtree(DATA)
    os.makedirs(os.path.join(DATA, "LICENSES"))
    for lic in ("bevietnampro_OFL.txt", "patrickhand_OFL.txt", "notoserif_OFL.txt"):
        shutil.copy(os.path.join(FONTS, lic), os.path.join(DATA, "LICENSES", lic.replace("_", "-")))
    make_text()
    if "--text-only" not in sys.argv:
        make_fonts()
