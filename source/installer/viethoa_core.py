"""Core install / uninstall logic of the Vietnamese patch for Do Not Feed the Monkeys.

The patch is applied onto the player's own game files:
  resources.assets      TextAsset `ko`  <- English text with Vietnamese translations merged in
                        TextAsset `koCredits` <- English credits with translated headers
  sharedassets2/3.assets  the 18 Korean-slot TextMeshPro fonts <- Vietnamese-capable SDF fonts
The Korean language slot becomes Vietnamese. Originals are kept in <game>/_VietHoa_backup.
"""
import hashlib, json, os, shutil, sys, zlib

PATCH_VERSION = "1.0"
FILES = ("resources.assets", "sharedassets2.assets", "sharedassets3.assets")
BACKUP_DIR = "_VietHoa_backup"
REG_PATH = r"Software\Fictiorama Studios\Do not feed the monkeys"


class PatchError(Exception):
    pass


def data_dir():
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "data")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ----------------------------------------------------------------- locating the game
def normalize_game_dir(path):
    """Accept the game folder, its dnftm_Data folder or the exe path. Return the game folder."""
    p = os.path.abspath(os.path.expanduser(path.strip().strip('"')))
    if os.path.isfile(p):
        p = os.path.dirname(p)
    if os.path.basename(p).lower() == "dnftm_data":
        p = os.path.dirname(p)
    return p


def check_game_dir(game):
    d = os.path.join(game, "dnftm_Data")
    if not os.path.isdir(d):
        raise PatchError(f"Không thấy thư mục dnftm_Data trong:\n{game}\nHãy chọn đúng thư mục cài game (thư mục chứa dnftm.exe).")
    for f in FILES + ("Managed/Assembly-CSharp-firstpass.dll",):
        if not os.path.isfile(os.path.join(d, f)):
            raise PatchError(f"Thiếu file {f} trong dnftm_Data. Thư mục game không hợp lệ hoặc bị hỏng.")
    return d


def find_steam_game():
    """Best-effort search of Steam libraries for the DNFTM folder."""
    roots = []
    try:
        import winreg
        for hive, key, val in ((winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
                               (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath")):
            try:
                with winreg.OpenKey(hive, key) as k:
                    roots.append(winreg.QueryValueEx(k, val)[0])
            except OSError:
                pass
    except ImportError:
        pass
    libs = []
    for r in roots:
        libs.append(r)
        vdf = os.path.join(r, "steamapps", "libraryfolders.vdf")
        if os.path.isfile(vdf):
            for line in open(vdf, encoding="utf-8", errors="ignore"):
                line = line.strip()
                if line.startswith('"path"'):
                    libs.append(line.split('"')[3].replace("\\\\", "\\"))
    for lib in libs:
        cand = os.path.join(lib, "steamapps", "common", "DNFTM")
        if os.path.isdir(os.path.join(cand, "dnftm_Data")):
            return os.path.normpath(cand)
    return None


# ----------------------------------------------------------------- state / backup
def state(game):
    """'none' | 'installed' | 'updated' (game files changed since install, e.g. by a Steam update)."""
    bdir = os.path.join(game, BACKUP_DIR)
    man = os.path.join(bdir, "manifest.json")
    if not os.path.isfile(man):
        return "none", None
    m = json.load(open(man, encoding="utf-8"))
    d = os.path.join(game, "dnftm_Data")
    for f in FILES:
        if sha256(os.path.join(d, f)) != m["patched"][f]:
            return "updated", m
    return "installed", m


def looks_patched(asset_env):
    """Detect our Vietnamese text in the `ko` slot (e.g. a manual install without backup)."""
    for o in asset_env.objects:
        if o.type.name == "TextAsset":
            t = o.read()
            if t.m_Name == "ko":
                s = t.m_Script
                return "TIẾNG VIỆT" in s[:200000] and "Hội Quan Sát Linh Trưởng" in s
    return False


# ----------------------------------------------------------------- patching
def _patch_text(env, log):
    text = json.load(open(os.path.join(data_dir(), "text.json"), encoding="utf-8"))
    credits_map = json.load(open(os.path.join(data_dir(), "credits.json"), encoding="utf-8"))
    objs = {}
    for o in env.objects:
        if o.type.name == "TextAsset":
            objs[o.read().m_Name] = o
    for need in ("en", "ko", "enCredits", "koCredits"):
        if need not in objs:
            raise PatchError(f"Không tìm thấy dữ liệu ngôn ngữ '{need}'. Phiên bản game không tương thích.")
    try:
        en = json.loads(objs["en"].read().m_Script.lstrip("﻿"))
    except ValueError:
        raise PatchError("Dữ liệu tiếng Anh của game không đọc được. Phiên bản game không tương thích.")
    applied = skipped = 0
    for sec, items in text.items():
        for k, (src, vi) in items.items():
            if sec in en and en[sec].get(k) == src:
                en[sec][k] = vi
                applied += 1
            else:
                skipped += 1
    total = applied + skipped
    if applied < total * 0.5:
        raise PatchError(f"Chỉ khớp {applied}/{total} chuỗi. Phiên bản game khác quá nhiều, đã dừng để tránh lỗi.")
    ko = objs["ko"].read()
    ko.m_Script = json.dumps(en, ensure_ascii=False, separators=(",", ":"))
    ko.save()
    src = objs["enCredits"].read().m_Script
    lines = src.split("\n")
    out = []
    for ln in lines:
        body = ln.rstrip("\r")
        out.append(credits_map.get(body, body) + ln[len(body):])
    kc = objs["koCredits"].read()
    kc.m_Script = "\n".join(out)
    kc.save()
    log(f"Văn bản: đã dịch {applied}/{total} chuỗi" + (f" ({skipped} chuỗi giữ tiếng Anh do game đã thay đổi)" if skipped else ""))


_NODE = None


def _font_node(game):
    global _NODE
    if _NODE is None:
        from UnityPy.helpers.TypeTreeGenerator import TypeTreeGenerator
        gen = TypeTreeGenerator("5.6.1f1")
        gen.load_local_dll_folder(os.path.join(game, "dnftm_Data", "Managed"))
        _NODE = gen.get_nodes_up("Assembly-CSharp-firstpass", "TMPro.TMP_FontAsset")
    return _NODE


def _patch_fonts(env, fn, game, log):
    meta = json.load(open(os.path.join(data_dir(), "fonts.json"), encoding="utf-8"))[fn]
    node = _font_node(game)
    objs = {o.path_id: o for o in env.objects}
    atlases = {}
    for pid_s, m in meta.items():
        pid = int(pid_s)
        if pid not in objs:
            raise PatchError(f"Không tìm thấy font #{pid} trong {fn}. Phiên bản game không tương thích.")
        tr = objs[pid].read_typetree(node)
        fi = tr["m_fontInfo"]
        if tr["m_Name"] != m["name"] or int(fi["AtlasWidth"]) != m["atlas_size"] or int(fi["Padding"]) != m["padding"]:
            raise PatchError(f"Font #{pid} trong {fn} không đúng như mong đợi. Phiên bản game không tương thích.")
        tr["m_glyphInfoList"] = [
            dict(id=g["id"], x=g["x"], y=g["y"], width=float(g["w"]), height=float(g["h"]),
                 xOffset=float(g["xo"]), yOffset=float(g["yo"]), xAdvance=float(g["adv"]), scale=1.0)
            for g in m["glyphs"]]
        newfi = dict(fi)
        newfi.update({k: float(v) if k != "CharacterCount" else int(v) for k, v in m["face"].items()})
        newfi["Name"] = m["font_name"]
        tr["m_fontInfo"] = newfi
        tr["m_kerningInfo"] = {"kerningPairs": []}
        objs[pid].save_typetree(tr, node)
        at = tr["atlas"]
        if at["m_FileID"] != 0 or at["m_PathID"] not in objs:
            raise PatchError(f"Atlas của font #{pid} không hợp lệ.")
        tex = objs[at["m_PathID"]].read()
        size = m["atlas_size"]
        if (tex.m_Width, tex.m_Height) != (size, size) or tex.m_TextureFormat != 1:
            raise PatchError(f"Atlas của font #{pid} không đúng định dạng.")
        if m["atlas_file"] not in atlases:
            atlases[m["atlas_file"]] = zlib.decompress(open(os.path.join(data_dir(), m["atlas_file"]), "rb").read())
        raw = atlases[m["atlas_file"]]
        tex.image_data = raw
        tex.m_CompleteImageSize = len(raw)
        tex.m_MipCount = 1
        tex.m_StreamData.offset = 0
        tex.m_StreamData.size = 0
        tex.m_StreamData.path = ""
        tex.save()
    log(f"Font: đã thay {len(meta)} font trong {fn}")


def install(game, log=print, set_language=True):
    import UnityPy
    game = normalize_game_dir(game)
    d = check_game_dir(game)
    bdir = os.path.join(game, BACKUP_DIR)
    st, man = state(game)
    # per file: if the live file is still our patched version, start from the backed-up original;
    # otherwise the live file is (a new) original, e.g. restored or updated by Steam.
    src = {}
    for f in FILES:
        live = os.path.join(d, f)
        if man and sha256(live) == man["patched"][f] and os.path.isfile(os.path.join(bdir, f)):
            src[f] = os.path.join(bdir, f)
        else:
            src[f] = live
    if st == "installed":
        log("Đã có bản Việt hóa, cài lại từ bản gốc đã sao lưu...")
    elif st == "updated":
        log("Game đã thay đổi kể từ lần cài trước (có thể do Steam cập nhật). Dùng file hiện tại làm bản gốc mới.")

    envs = {}
    for f in FILES:
        with open(src[f], "rb") as fh:
            envs[f] = UnityPy.load(fh.read())  # in memory: no handle left on game files
    if src["resources.assets"].startswith(d) and looks_patched(envs["resources.assets"]):
        raise PatchError("File game đã bị Việt hóa từ trước nhưng không có bản sao lưu.\n"
                         "Hãy vào Steam: chuột phải game > Properties > Installed Files > "
                         "Verify integrity of game files, rồi chạy lại trình cài.")

    log("Đang dịch văn bản...")
    _patch_text(envs["resources.assets"], log)
    log("Đang thay font (mất khoảng 1 phút)...")
    for f in FILES[1:]:
        _patch_fonts(envs[f], f, game, log)
    payloads = {f: envs[f].file.save() for f in FILES}
    del envs

    # back up every original that comes from the live folder, before touching game files
    os.makedirs(bdir, exist_ok=True)
    for f in FILES:
        if src[f] != os.path.join(bdir, f):
            tmp = os.path.join(bdir, f + ".tmp")
            shutil.copy2(src[f], tmp)
            os.replace(tmp, os.path.join(bdir, f))
    log(f"Đã sao lưu file gốc vào {bdir}")
    originals = {f: sha256(os.path.join(bdir, f)) for f in FILES}

    for f in FILES:
        dst = os.path.join(d, f)
        tmp = dst + ".viethoa_tmp"
        with open(tmp, "wb") as fh:
            fh.write(payloads[f])
        os.replace(tmp, dst)
    manifest = dict(version=PATCH_VERSION, original=originals,
                    patched={f: sha256(os.path.join(d, f)) for f in FILES})
    json.dump(manifest, open(os.path.join(bdir, "manifest.json"), "w", encoding="utf-8"), indent=1)
    if set_language:
        set_lang("ko", log)
    log("HOÀN TẤT: đã cài Việt hóa.")


def uninstall(game, log=print):
    game = normalize_game_dir(game)
    d = check_game_dir(game)
    bdir = os.path.join(game, BACKUP_DIR)
    man_path = os.path.join(bdir, "manifest.json")
    if not os.path.isfile(man_path):
        raise PatchError("Không tìm thấy bản sao lưu (_VietHoa_backup).\n"
                         "Để trả game về nguyên gốc, hãy vào Steam: chuột phải game > Properties > "
                         "Installed Files > Verify integrity of game files.")
    man = json.load(open(man_path, encoding="utf-8"))
    st, _ = state(game)
    if st == "updated":
        log("Lưu ý: file game đã thay đổi sau khi cài (có thể do Steam cập nhật). Vẫn khôi phục bản sao lưu.")
    for f in FILES:
        if sha256(os.path.join(bdir, f)) != man["original"][f]:
            raise PatchError(f"Bản sao lưu {f} bị hỏng. Hãy dùng Verify integrity of game files trên Steam.")
    for f in FILES:
        dst = os.path.join(d, f)
        tmp = dst + ".viethoa_tmp"
        shutil.copy2(os.path.join(bdir, f), tmp)
        os.replace(tmp, dst)
    shutil.rmtree(bdir)
    if get_lang() == "ko":
        set_lang("en", log)
    log("HOÀN TẤT: đã gỡ Việt hóa, game trở về nguyên gốc.")


# ----------------------------------------------------------------- language setting (PlayerPrefs)
def _pref_name(key):
    h = 5381
    for c in key:
        h = ((h * 33) ^ ord(c)) & 0xFFFFFFFF
    return f"{key}_h{h}"


def get_lang():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH) as k:
            v, _ = winreg.QueryValueEx(k, _pref_name("lang"))
            return bytes(v).rstrip(b"\0").decode("utf-8", "ignore")
    except (OSError, ImportError):
        return None


def set_lang(code, log=print):
    try:
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_PATH) as k:
            winreg.SetValueEx(k, _pref_name("lang"), 0, winreg.REG_BINARY, code.encode() + b"\0")
        log("Đã đặt ngôn ngữ game: " + ("Tiếng Việt" if code == "ko" else "English"))
    except (OSError, ImportError):
        log("Không đặt được ngôn ngữ tự động. Hãy vào SETTINGS > LANGUAGE trong game.")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["install", "uninstall", "status"])
    ap.add_argument("game", nargs="?")
    a = ap.parse_args()
    g = a.game or find_steam_game()
    if not g:
        raise SystemExit("game folder not found")
    try:
        if a.action == "install":
            install(g)
        elif a.action == "uninstall":
            uninstall(g)
        else:
            print(state(normalize_game_dir(g))[0], get_lang())
    except PatchError as e:
        raise SystemExit("LỖI: " + str(e))
