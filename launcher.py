"""
VoiceType Launcher — скачивает приложение и запускает его.
"""
import os, sys, zipfile, threading, subprocess, tempfile, shutil
import tkinter as tk
import urllib.request as ur

APP_URL   = "https://github.com/maslovserg-hub/my-voice-assistent/releases/download/v1.0/VoiceType_release.zip"
INSTALL_DIR = os.path.join(os.environ.get("APPDATA", "C:/VoiceType"), "VoiceType")
EXE_PATH    = os.path.join(INSTALL_DIR, "VoiceType", "VoiceType.exe")

BG, ACC, WHITE, GRAY = "#1a1a2e", "#e05a00", "#f8f8f2", "#888888"

def already_installed():
    return os.path.isfile(EXE_PATH)

def launch():
    subprocess.Popen([EXE_PATH], creationflags=0x00000008)
    sys.exit(0)

def run_installer():
    if already_installed():
        launch()

    win = tk.Tk()
    win.title("VoiceType — установка")
    win.configure(bg=BG)
    win.resizable(False, False)
    win.geometry("400x220")
    win.eval("tk::PlaceWindow . center")
    win.protocol("WM_DELETE_WINDOW", sys.exit)

    tk.Label(win, text="VoiceType", font=("Segoe UI", 18, "bold"),
             fg=ACC, bg=BG).pack(pady=(24, 4))

    status_var = tk.StringVar(value="Подготовка…")
    tk.Label(win, textvariable=status_var, font=("Segoe UI", 10),
             fg=WHITE, bg=BG).pack(pady=(0, 12))

    canvas = tk.Canvas(win, width=340, height=8, bg="#252540", highlightthickness=0)
    canvas.pack()
    bar = canvas.create_rectangle(0, 0, 0, 8, fill=ACC, outline="")

    def set_progress(frac, text):
        canvas.coords(bar, 0, 0, int(340 * frac), 8)
        canvas.update()
        status_var.set(text)
        win.update()

    def _do():
        try:
            os.makedirs(INSTALL_DIR, exist_ok=True)
            zip_path = os.path.join(INSTALL_DIR, "VoiceType.zip")

            # Скачать zip (3 попытки)
            for attempt in range(3):
                try:
                    req = ur.Request(APP_URL, headers={"User-Agent": "VoiceType-Launcher/1.0"})
                    with ur.urlopen(req, timeout=300) as src:
                        total = int(src.headers.get("Content-Length", 0))
                        downloaded = 0
                        with open(zip_path, "wb") as f:
                            while True:
                                buf = src.read(65536)
                                if not buf:
                                    break
                                f.write(buf)
                                downloaded += len(buf)
                                frac = (downloaded / total * 0.85) if total else 0.1
                                mb = downloaded / 1024 / 1024
                                win.after(0, set_progress, frac,
                                          f"Скачивание: {mb:.0f} МБ")
                    break
                except Exception as e:
                    if attempt < 2:
                        win.after(0, status_var.set, f"Повтор {attempt+2}/3…")
                        import time; time.sleep(3)
                    else:
                        raise

            # Распаковать
            win.after(0, set_progress, 0.88, "Распаковка…")
            with zipfile.ZipFile(zip_path) as z:
                z.extractall(INSTALL_DIR)
            os.unlink(zip_path)

            win.after(0, set_progress, 1.0, "Готово! Запускаю…")
            win.after(800, launch)

        except Exception as e:
            win.after(0, status_var.set, f"Ошибка: {e}")

    threading.Thread(target=_do, daemon=True).start()
    win.mainloop()

if __name__ == "__main__":
    run_installer()
