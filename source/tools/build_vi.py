"""Build the Vietnamese patch for Do Not Feed the Monkeys.

Always reads pristine files from DNFTM_backup_original and writes patched copies
into the game's dnftm_Data folder, so it can be re-run safely.

Steps:
  1. Merge translation overlays (vietnamese/translations/*.json) onto en.json,
     validate tags/placeholders, write result into the `ko` TextAsset.
  2. Regenerate the Korean-slot TMP font assets (glyph table + SDF atlas)
     from Vietnamese-capable TTFs.

Usage: python build_vi.py [--text-only | --fonts-only]
"""
import copy, glob, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))           # ...\DNFTM
GAME = os.path.join(ROOT, "dnftm_Data")
BACKUP = os.path.join(os.path.dirname(ROOT), "DNFTM_backup_original")
TRANS = os.path.join(ROOT, "vietnamese", "translations")
OUT = os.path.join(ROOT, "vietnamese", "build")
sys.path.insert(0, HERE)

import UnityPy  # noqa: E402

TOKEN_RE = re.compile(r"<[^>]+>|\[/?[A-Za-z0-9_ ]+\]|\$?\{%?[^}]*\}|%[sd]|_[A-Za-z0-9]+_|@[A-Za-z0-9]+")


def tokens(s):
    t = TOKEN_RE.findall(s)
    t.append(f"pipes={s.count('|')}")
    t.append(f"lead_ws={s[:1].isspace()}")
    return sorted(t)


DISPLAY_ANGLE_KEYS = {"endings.76", "endings.77"}


def merge_translations(en):
    vi = copy.deepcopy(en)
    problems, count = [], 0
    for fp in sorted(glob.glob(os.path.join(TRANS, "*.json"))):
        overlay = json.load(open(fp, encoding="utf-8"))
        for sec, items in overlay.items():
            if sec not in en:
                problems.append(f"{os.path.basename(fp)}: unknown section {sec}")
                continue
            for key, text in items.items():
                if key not in en[sec]:
                    problems.append(f"{os.path.basename(fp)}: unknown key {sec}.{key}")
                    continue
                src = en[sec][key]
                if not isinstance(src, str) or not isinstance(text, str):
                    problems.append(f"{sec}.{key}: non-string value")
                    continue
                if f"{sec}.{key}" in DISPLAY_ANGLE_KEYS:
                    # <Landlady>, <Kitchen>... are literal on-screen labels, not TMP tags: translate text, keep count
                    norm = lambda x: sorted("<LABEL>" if re.fullmatch(r"<[^/=>]*[^>a-z/=][^>]*>", t) and t not in ("<b>","<i>","<s>") else t for t in tokens(x))
                    ok = norm(src) == norm(text)
                else:
                    ok = tokens(src) == tokens(text)
                if not ok:
                    problems.append(f"{sec}.{key}: token mismatch {tokens(src)} vs {tokens(text)}")
                    continue
                vi[sec][key] = text
                count += 1
    return vi, count, problems


# credits: enCredits with role headers translated, written into koCredits.
# Lines containing "*" start one of exactly 4 pages (MenuController.showCredits) - keep them.
CREDITS_MAP = {
    "<u>Game Idea</u>": "<u>Ý tưởng game</u>",
    "<u>Programming</u>": "<u>Lập trình</u>",
    "<u>Narrative Design</u>": "<u>Thiết kế cốt truyện</u>",
    "<u>Game Design</u>": "<u>Thiết kế game</u>",
    "<u>Art</u>": "<u>Đồ họa</u>",
    "<u>Sound Design</u>": "<u>Thiết kế âm thanh</u>",
    "<u>Graphic Design</u>": "<u>Thiết kế đồ họa</u>",
    "<u>Proofreading</u>": "<u>Hiệu đính</u>",
    "<u>Production</u>": "<u>Sản xuất</u>",
    "<u>Producers</u>": "<u>Nhà sản xuất</u>",
    "<u>Partners Relations</u>": "<u>Quan hệ đối tác</u>",
    "<u>Marketing & PR</u>": "<u>Tiếp thị & PR</u>",
    "<u>Marketing</u>": "<u>Tiếp thị</u>",
    "<u>Localization</u>": "<u>Bản địa hóa</u>",
    "<u>QA</u>": "<u>Kiểm thử (QA)</u>",
    "<u>CEO</u>": "<u>Giám đốc điều hành</u>",
    "<u>PR</u>": "<u>Quan hệ công chúng</u>",
    "<u>Digital Key Account</u>": "<u>Quản lý khách hàng kỹ thuật số</u>",
    "<u>Beta testing</u>": "<u>Thử nghiệm beta</u>",
    "<u>Gameplay Feedback</u>": "<u>Góp ý lối chơi</u>",
    "*Fictiorama thanks": "*Fictiorama xin cảm ơn",
    "Mom & Dad": "Bố & Mẹ",
}


def build_credits(objs):
    src = objs["enCredits"].read().m_Script
    lines = src.split(chr(10))
    out = []
    for ln in lines:
        body = ln.rstrip(chr(13))
        tail = ln[len(body):]
        out.append(CREDITS_MAP.get(body, body) + tail)
    text = chr(10).join(out)
    assert text.count("*") == src.count("*") == 4 and len(out) == len(lines)
    ko = objs["koCredits"].read()
    ko.m_Script = text
    ko.save()
    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, "viCredits.txt"), "w", encoding="utf-8", newline="").write(text)
    print("credits: koCredits replaced with Vietnamese headers")


def build_text():
    env = UnityPy.load(os.path.join(BACKUP, "resources.assets"))
    objs = {o.read().m_Name: o for o in env.objects if o.type.name == "TextAsset"}
    en_obj, ko_obj = objs["en"], objs["ko"]
    en_text = en_obj.read().m_Script
    en = json.loads(en_text.lstrip("\ufeff"))
    vi, count, problems = merge_translations(en)
    for p in problems:
        print("  !!", p)
    if problems:
        raise SystemExit("translation validation failed")
    payload = json.dumps(vi, ensure_ascii=False, separators=(",", ":"))
    json.loads(payload)
    ko = ko_obj.read()
    ko.m_Script = payload
    ko.save()
    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, "vi.json"), "w", encoding="utf-8").write(payload)
    build_credits(objs)
    write_asset(env, "resources.assets")
    print(f"text: {count} translated strings written into slot 'ko'")


# --- fonts -----------------------------------------------------------------
WIN = r"C:\Windows\Fonts"
# path_id -> (ttf, ttc index, render point size)
FONT_PLAN = {
    "sharedassets2.assets": {
        253: ("arialbd.ttf", 0, 48),     # BM DoHyeon   <- yetbumbler
        254: ("verdana.ttf", 0, 48),     # Bandal       <- calculon
        255: ("segoeuib.ttf", 0, 48),    # Bangwool     <- arpegius
        256: ("candarai.ttf", 0, 61),    # Gaegu        <- Sketchy (handwriting, pad 5)
        257: ("verdanab.ttf", 0, 48),    # HANDotum     <- blocktopia
        258: ("tahomabd.ttf", 0, 48),    # chungdoongori<- pixelflag
        259: ("calibri.ttf", 0, 48),     # LotteMart    <- loxical
        260: ("cambria.ttc", 0, 48),     # Myeongjo     <- tempesta / newspaper
        261: ("tahoma.ttf", 0, 48),      # neodgm       <- blrrpixt fuera monitor
        262: ("tahoma.ttf", 0, 48),      # neodgm       <- main UI / monitor texts
    },
    "sharedassets3.assets": {
        11764: ("arialbd.ttf", 0, 48),   # BM-HANNA     <- ARIAL / STAMPACT
        11765: ("arialbd.ttf", 0, 48),   # BM JUA
        11766: ("tahoma.ttf", 0, 48),    # Goobongdoorisam <- scoreboard / numbered
        11767: ("tahoma.ttf", 0, 48),
        11768: ("tahoma.ttf", 0, 48),
        11769: ("tahoma.ttf", 0, 48),
        11770: ("tahoma.ttf", 0, 48),
        11771: ("tahoma.ttf", 0, 48),
    },
}


def build_fonts():
    from UnityPy.helpers.TypeTreeGenerator import TypeTreeGenerator
    from gen_sdf import build as gen_build
    import numpy as np

    gen = TypeTreeGenerator("5.6.1f1")
    gen.load_local_dll_folder(os.path.join(GAME, "Managed"))
    node = gen.get_nodes_up("Assembly-CSharp-firstpass", "TMPro.TMP_FontAsset")
    cache = {}
    for fn, plan in FONT_PLAN.items():
        env = UnityPy.load(os.path.join(BACKUP, fn))
        objs = {o.path_id: o for o in env.objects}
        for pid, (ttf, idx, pt) in plan.items():
            tr = objs[pid].read_typetree(node)
            fi = tr["m_fontInfo"]
            pad, atlas = int(fi["Padding"]), int(fi["AtlasWidth"])
            target = fi["CapHeight"] / fi["PointSize"] if fi["CapHeight"] > 0 else None
            key = (ttf, idx, pt, pad, atlas, round(target or 0, 4))
            if key not in cache:
                cache[key] = gen_build(os.path.join(WIN, ttf), pt, pad, atlas, idx, target)
            glyphs, face, A, used = cache[key]
            tr["m_glyphInfoList"] = [
                dict(id=g["id"], x=g["x"], y=g["y"], width=float(g["w"]), height=float(g["h"]),
                     xOffset=float(g["xo"]), yOffset=float(g["yo"]), xAdvance=float(g["adv"]), scale=1.0)
                for g in glyphs]
            newfi = dict(fi)
            newfi.update({k: float(v) if k != "CharacterCount" else int(v) for k, v in face.items()})
            newfi["Name"] = os.path.splitext(ttf)[0]
            tr["m_fontInfo"] = newfi
            tr["m_kerningInfo"] = {"kerningPairs": []}
            objs[pid].save_typetree(tr, node)
            # atlas texture
            at = tr["atlas"]
            assert at["m_FileID"] == 0
            tex = objs[at["m_PathID"]].read()
            assert (tex.m_Width, tex.m_Height) == (atlas, atlas) and tex.m_TextureFormat == 1
            raw = np.flipud(A).tobytes()
            tex.image_data = raw
            tex.m_CompleteImageSize = len(raw)
            tex.m_MipCount = 1
            tex.m_StreamData.offset = 0
            tex.m_StreamData.size = 0
            tex.m_StreamData.path = ""
            tex.save()
            print(f"font {fn}:{pid} {tr['m_Name']!r} <- {ttf} ({len(glyphs)} glyphs, rows {used}/{atlas})")
        write_asset(env, fn)


def write_asset(env, fn):
    data = env.file.save()
    dst = os.path.join(GAME, fn)
    tmp = dst + ".vi_tmp"
    open(tmp, "wb").write(data)
    os.replace(tmp, dst)
    print(f"wrote {dst} ({len(data)} bytes)")


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if arg != "--fonts-only":
        build_text()
    if arg != "--text-only":
        build_fonts()
