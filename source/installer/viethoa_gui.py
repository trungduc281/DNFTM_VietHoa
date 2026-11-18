"""Windows GUI for the Vietnamese patch of Do Not Feed the Monkeys."""
import os, queue, sys, threading, traceback
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import viethoa_core as core

TITLE = "Việt hóa Do Not Feed the Monkeys"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(TITLE)
        self.geometry("640x430")
        self.minsize(560, 380)
        self.q = queue.Queue()
        self.busy = False

        pad = dict(padx=12, pady=6)
        tk.Label(self, text=TITLE, font=("Segoe UI", 14, "bold")).pack(anchor="w", **pad)
        tk.Label(self, text="Dán hoặc chọn thư mục cài game (thư mục chứa dnftm.exe):",
                 font=("Segoe UI", 10)).pack(anchor="w", padx=12)

        row = tk.Frame(self)
        row.pack(fill="x", **pad)
        self.path = tk.StringVar(value=core.find_steam_game() or "")
        self.path.trace_add("write", lambda *_: self.refresh())
        tk.Entry(row, textvariable=self.path, font=("Segoe UI", 10)).pack(side="left", fill="x", expand=True)
        tk.Button(row, text="Chọn...", command=self.browse).pack(side="left", padx=(6, 0))

        self.status = tk.Label(self, text="", font=("Segoe UI", 10, "bold"))
        self.status.pack(anchor="w", padx=12)

        btns = tk.Frame(self)
        btns.pack(fill="x", **pad)
        self.b_install = tk.Button(btns, text="Cài Việt hóa", width=18, height=2,
                                   font=("Segoe UI", 10, "bold"), command=lambda: self.run("install"))
        self.b_install.pack(side="left")
        self.b_uninstall = tk.Button(btns, text="Gỡ Việt hóa", width=18, height=2,
                                     font=("Segoe UI", 10), command=lambda: self.run("uninstall"))
        self.b_uninstall.pack(side="left", padx=8)
        self.bar = ttk.Progressbar(btns, mode="indeterminate", length=150)
        self.bar.pack(side="right")

        self.log = tk.Text(self, height=10, font=("Consolas", 9), state="disabled", wrap="word")
        self.log.pack(fill="both", expand=True, padx=12, pady=(0, 6))
        tk.Label(self, text="Hãy tắt game trước khi cài hoặc gỡ. Bản sao lưu file gốc nằm trong <thư mục game>\\_VietHoa_backup.",
                 font=("Segoe UI", 8), fg="#555").pack(anchor="w", padx=12, pady=(0, 8))
        if not self.path.get():
            self.write("Không tự tìm thấy game qua Steam. Hãy dán đường dẫn hoặc bấm Chọn...")
        self.refresh()
        self.after(100, self.poll)

    def browse(self):
        d = filedialog.askdirectory(title="Chọn thư mục game DNFTM")
        if d:
            self.path.set(os.path.normpath(d))

    def write(self, msg):
        self.log.configure(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def refresh(self):
        if self.busy:
            return
        g = core.normalize_game_dir(self.path.get()) if self.path.get().strip() else ""
        try:
            core.check_game_dir(g)
            st, _ = core.state(g)
            text = {"none": "Trạng thái: chưa cài Việt hóa",
                    "installed": "Trạng thái: ĐÃ cài Việt hóa",
                    "updated": "Trạng thái: game đã thay đổi sau khi cài (cần cài lại)"}[st]
            self.status.configure(text=text, fg="#1a7f37" if st == "installed" else "#9a6700")
            self.b_install.configure(state="normal",
                                     text="Cài lại Việt hóa" if st != "none" else "Cài Việt hóa")
            self.b_uninstall.configure(state="normal" if st != "none" else "disabled")
        except core.PatchError:
            self.status.configure(text="Chưa chọn đúng thư mục game", fg="#cf222e")
            self.b_install.configure(state="disabled")
            self.b_uninstall.configure(state="disabled")
        except OSError as e:
            self.status.configure(text=f"Không đọc được thư mục: {e}", fg="#cf222e")

    def run(self, action):
        g = self.path.get()
        if action == "uninstall" and not messagebox.askyesno(TITLE, "Gỡ Việt hóa và trả game về nguyên gốc?"):
            return
        self.busy = True
        self.b_install.configure(state="disabled")
        self.b_uninstall.configure(state="disabled")
        self.bar.start(12)

        def work():
            try:
                fn = core.install if action == "install" else core.uninstall
                fn(g, log=lambda m: self.q.put(("log", m)))
                self.q.put(("done", action))
            except core.PatchError as e:
                self.q.put(("error", str(e)))
            except PermissionError:
                self.q.put(("error", "Không ghi được file game. Hãy tắt game (và Steam nếu đang cập nhật) rồi thử lại."))
            except Exception:
                self.q.put(("error", "Lỗi không mong muốn:\n" + traceback.format_exc()))

        threading.Thread(target=work, daemon=True).start()

    def poll(self):
        try:
            while True:
                kind, msg = self.q.get_nowait()
                if kind == "log":
                    self.write(msg)
                    continue
                self.busy = False
                self.bar.stop()
                if kind == "done":
                    messagebox.showinfo(TITLE, "Đã cài Việt hóa xong. Mở game và chơi thôi!" if msg == "install"
                                        else "Đã gỡ Việt hóa. Game đã trở về nguyên gốc.")
                else:
                    self.write("LỖI: " + msg)
                    messagebox.showerror(TITLE, msg)
                self.refresh()
        except queue.Empty:
            pass
        self.after(100, self.poll)


if __name__ == "__main__":
    if len(sys.argv) > 1:          # CLI mode: viethoa.exe install|uninstall|status [game]
        sys.argv[0] = "viethoa_core"
        import runpy
        runpy.run_module("viethoa_core", run_name="__main__")
    else:
        App().mainloop()
