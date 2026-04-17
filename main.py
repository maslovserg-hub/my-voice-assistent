"""
VoiceType — голосовой ввод в любое поле Windows.
Right Ctrl  — начать / остановить и ВСТАВИТЬ текст
Esc / ✕     — остановить и ОТМЕНИТЬ (текст не вставляется)
"""
import os, re, math, threading, tempfile, time, sys
import tkinter as tk
import numpy as np

# Подавить мелькание консольных окон от подпроцессов (torch, soundfile и др.)
if sys.platform == "win32":
    import subprocess as _sp
    _Popen_orig = _sp.Popen.__init__
    def _Popen_no_window(self, *a, creationflags=0, **kw):
        _Popen_orig(self, *a, creationflags=creationflags | 0x08000000, **kw)
    _sp.Popen.__init__ = _Popen_no_window

# Один экземпляр — Windows mutex
import ctypes
_mutex = ctypes.windll.kernel32.CreateMutexW(None, True, "VoiceType_SingleInstance")
if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
    import tkinter.messagebox as mb
    _r = tk.Tk(); _r.withdraw()
    mb.showwarning("VoiceType", "VoiceType уже запущен.")
    sys.exit(0)
import sounddevice as sd
import soundfile as sf
from pynput import keyboard
from PIL import Image, ImageDraw
import pystray

DEFAULT_CACHE = "C:/gigaam_cache"
MODEL_NAME    = "v3_e2e_ctc"
SAMPLE_RATE   = 16000
BLOCKSIZE     = 1600
SILENCE_TH    = 0.018
SILENCE_BLK   = 15   # 1.5 сек тишины → сброс чанка
MAX_BLOCKS    = 150  # 15 сек максимум на чанк

# ── Мастер первого запуска ────────────────────────────────────────────────────
import gigaam as _gigaam

def model_exists(path: str) -> bool:
    ckpt = os.path.join(path, f"{MODEL_NAME}.ckpt")
    tok  = os.path.join(path, f"{MODEL_NAME}_tokenizer.model")
    return (os.path.isfile(ckpt) and os.path.getsize(ckpt) > 1_000_000 and
            os.path.isfile(tok)  and os.path.getsize(tok)  > 1_000)

def run_setup_wizard() -> str:
    """Показать диалог выбора/скачивания модели. Возвращает путь к папке."""
    import tkinter.filedialog as fd

    result = {"path": None}
    BG, PILL, ACC = "#1a1a2e", "#252540", "#e05a00"
    WHITE, GRAY = "#f8f8f2", "#888888"

    win = tk.Tk()
    win.title("VoiceType — первый запуск")
    win.configure(bg=BG)
    win.resizable(False, False)
    win.geometry("420x260")
    win.eval("tk::PlaceWindow . center")

    tk.Label(win, text="VoiceType", font=("Segoe UI", 18, "bold"),
             fg=ACC, bg=BG).pack(pady=(24, 4))
    tk.Label(win, text="Модель GigaAM не найдена. Что сделать?",
             font=("Segoe UI", 11), fg=WHITE, bg=BG).pack(pady=(0, 20))

    status_var = tk.StringVar(value="")
    status = tk.Label(win, textvariable=status_var,
                      font=("Segoe UI", 9), fg=GRAY, bg=BG)
    status.pack()

    progress = tk.Canvas(win, width=360, height=8, bg=PILL,
                         highlightthickness=0)
    progress.pack(pady=6)
    prog_bar = progress.create_rectangle(0, 0, 0, 8, fill=ACC, outline="")

    def update_progress(fraction: float):
        progress.coords(prog_bar, 0, 0, int(360 * fraction), 8)
        progress.update()

    def browse():
        folder = fd.askdirectory(title="Выберите папку с моделью GigaAM")
        if not folder:
            return
        if model_exists(folder):
            result["path"] = folder
            win.destroy()
        else:
            status_var.set("Модель не найдена в этой папке. Нужны файлы v3_e2e_ctc.*")

    def download():
        btn_dl.config(state="disabled")
        btn_br.config(state="disabled")
        cache = DEFAULT_CACHE
        os.makedirs(cache, exist_ok=True)
        # Удалить пустые файлы от предыдущей попытки
        for fname in (f"{MODEL_NAME}.ckpt", f"{MODEL_NAME}_tokenizer.model"):
            fp = os.path.join(cache, fname)
            if os.path.isfile(fp) and os.path.getsize(fp) < 1_000:
                os.unlink(fp)

        TARGET_BYTES = 650 * 1024 * 1024
        ckpt_path = os.path.join(cache, f"{MODEL_NAME}.ckpt")
        done = threading.Event()

        def _monitor():
            while not done.is_set():
                try:
                    if os.path.isfile(ckpt_path):
                        sz = os.path.getsize(ckpt_path)
                        mb = sz / 1024 / 1024
                        frac = min(sz / TARGET_BYTES, 0.99)
                        win.after(0, lambda f=frac, m=mb: (
                            update_progress(f),
                            status_var.set(f"Скачивание: {m:.0f} / ~650 МБ")
                        ))
                except Exception:
                    pass
                time.sleep(1)

        def _do():
            for attempt in range(15):
                try:
                    _gigaam.load_model(MODEL_NAME, device="cpu", download_root=cache)
                    result["path"] = cache
                    done.set()
                    win.after(0, lambda: update_progress(1.0))
                    win.after(500, win.destroy)
                    return
                except Exception as e:
                    err = str(e)[:50]
                    if attempt < 14:
                        win.after(0, lambda a=attempt, s=err:
                            status_var.set(f"Повтор {a+2}/15… ({s})"))
                        time.sleep(4)
                    else:
                        done.set()
                        win.after(0, lambda s=err: status_var.set(f"Ошибка: {s}"))
                        win.after(0, lambda: btn_dl.config(state="normal"))
                        win.after(0, lambda: btn_br.config(state="normal"))

        threading.Thread(target=_monitor, daemon=True).start()
        threading.Thread(target=_do, daemon=True).start()

    btn_frame = tk.Frame(win, bg=BG)
    btn_frame.pack(pady=12)

    btn_style = dict(font=("Segoe UI", 11), relief="flat",
                     padx=18, pady=8, cursor="hand2")
    btn_br = tk.Button(btn_frame, text="Выбрать папку", bg=PILL, fg=WHITE,
                       activebackground="#3a3a5c", activeforeground=WHITE,
                       command=browse, **btn_style)
    btn_br.pack(side="left", padx=8)

    btn_dl = tk.Button(btn_frame, text="Скачать модель", bg=ACC, fg=WHITE,
                       activebackground="#c04800", activeforeground=WHITE,
                       command=download, **btn_style)
    btn_dl.pack(side="left", padx=8)

    win.protocol("WM_DELETE_WINDOW", sys.exit)
    win.mainloop()

    if not result["path"]:
        sys.exit(0)
    return result["path"]

# ── Загрузка модели ───────────────────────────────────────────────────────────
CACHE_DIR = DEFAULT_CACHE
if not model_exists(CACHE_DIR):
    CACHE_DIR = run_setup_wizard()

print("Загрузка GigaAM v3...", flush=True)
model = _gigaam.load_model(MODEL_NAME, device="cpu", download_root=CACHE_DIR)
print("Готово. Right Ctrl — начать запись.", flush=True)

recording   = False
cancelled   = False
current_rms = 0.0
kb_ctrl     = keyboard.Controller()
tr_lock     = threading.Lock()

NOISE_Y = re.compile(r'(?:^|(?<= ))[ыЫ](?=[а-яёА-ЯЁ])')

def clean(text):
    def _filter_latin(m):
        w = m.group()
        # Оставляем только латинские слова с гласными (настоящий английский)
        if any(c in 'aeiouAEIOU' for c in w) and len(w) >= 3:
            return w
        return ''
    text = re.sub(r'[a-zA-Z]+', _filter_latin, text).strip()
    text = NOISE_Y.sub('', text).strip()
    text = re.sub(r' {2,}', ' ', text)
    return text

def trim_end(audio, thr=SILENCE_TH):
    rms = [np.sqrt(np.mean(audio[i:i+BLOCKSIZE]**2))
           for i in range(0, len(audio), BLOCKSIZE)]
    last = next((i for i,r in enumerate(reversed(rms)) if r >= thr), None)
    if last is None: return np.array([], dtype=np.float32)
    return audio[:(len(rms)-last)*BLOCKSIZE]

def trim_start(audio, thr=SILENCE_TH):
    rms = [np.sqrt(np.mean(audio[i:i+BLOCKSIZE]**2))
           for i in range(0, len(audio), BLOCKSIZE)]
    first = next((i for i, r in enumerate(rms) if r >= thr), None)
    if first is None: return np.array([], dtype=np.float32)
    return audio[first*BLOCKSIZE:]

# ── Оверлей ──────────────────────────────────────────────────────────────────
class Overlay:
    W, H   = 72, 38
    TRANSP = "#010101"
    BG     = "#1a1a35"
    ACCENT = "#ff6b00"
    GRAY   = "#3a3a60"
    N_BARS = 5
    BAR_W  = 3

    def __init__(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=self.TRANSP)
        self.root.wm_attributes("-transparentcolor", self.TRANSP)
        self.root.wm_attributes("-alpha", 0.70)
        self.root.withdraw()

        self.cv = tk.Canvas(self.root, width=self.W, height=self.H,
                            bg=self.TRANSP, highlightthickness=0)
        self.cv.pack()

        self.bars = []
        total = self.N_BARS * self.BAR_W + (self.N_BARS - 1) * 5
        x0 = (self.W - total) // 2
        for i in range(self.N_BARS):
            x = x0 + i * (self.BAR_W + 5)
            cy = self.H // 2
            b = self.cv.create_rectangle(x, cy-1, x+self.BAR_W, cy+1,
                                         fill=self.GRAY, outline="", tags="bar")
            self.bars.append(b)

        self.cv.bind("<ButtonPress-1>", self._ds)
        self.cv.bind("<B1-Motion>",     self._dm)
        self._dx = self._dy = 0

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{self.W}x{self.H}+{(sw-self.W)//2}+{sh-self.H-64}")

        self._mic_active = False
        self._phase = 0.0
        self._q = []
        self._poll()
        self._anim()

    def _draw_bg(self):
        self.cv.create_oval(1, 1, self.W-1, self.H-1,
                            fill=self.BG, outline="")

    def _ds(self, e): self._dx, self._dy = e.x_root, e.y_root
    def _dm(self, e):
        dx, dy = e.x_root-self._dx, e.y_root-self._dy
        self.root.geometry(f"+{self.root.winfo_x()+dx}+{self.root.winfo_y()+dy}")
        self._dx, self._dy = e.x_root, e.y_root

    def _poll(self):
        while self._q: self._q.pop(0)()
        self.root.after(40, self._poll)

    def call(self, fn): self._q.append(fn)

    def show(self):
        def _u():
            self._mic_active = True
            self.root.deiconify()
        self.call(_u)

    def hide(self):
        def _u():
            self._mic_active = False
            self.root.withdraw()
        self.call(_u)

    def _anim(self):
        self._phase += 0.25
        mh = self.H // 2 - 4
        total = self.N_BARS * self.BAR_W + (self.N_BARS - 1) * 8
        x0 = (self.W - total) // 2

        total = self.N_BARS * self.BAR_W + (self.N_BARS - 1) * 5
        x0 = (self.W - total) // 2
        for i, b in enumerate(self.bars):
            x = x0 + i * (self.BAR_W + 5)
            cy = self.H // 2
            if self._mic_active:
                lvl = min(current_rms * 22 + 0.18, 1.0)
                h = max(2, int(mh * lvl * abs(math.sin(self._phase + i * 1.2))))
                color = self.ACCENT
            else:
                h = 2
                color = self.GRAY
            self.cv.coords(b, x, cy - h, x + self.BAR_W, cy + h)
            self.cv.itemconfig(b, fill=color)

        self.root.after(45, self._anim)

    def run(self): self.root.mainloop()

overlay = Overlay()

# ── Логика ───────────────────────────────────────────────────────────────────
def normalize(audio):
    peak = np.max(np.abs(audio))
    return audio / peak * 0.95 if peak > 0.01 else audio

def transcribe_and_type(audio):
    global cancelled
    audio = trim_start(audio)
    audio = trim_end(audio)
    if len(audio) < SAMPLE_RATE * 0.3:
        return
    audio = normalize(audio)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False, dir=CACHE_DIR) as f:
        tmp = f.name
    try:
        sf.write(tmp, audio, SAMPLE_RATE, subtype="PCM_16")
        with tr_lock:
            result = model.transcribe(tmp)
            text = clean(result.text.strip())
            if text and not cancelled:
                print(f"  → {text}", flush=True)
                kb_ctrl.type(text + " ")
    finally:
        try: os.unlink(tmp)
        except: pass

_blocks   = []
_silence  = 0

def _flush():
    global _blocks, _silence
    if _blocks:
        audio = np.concatenate(_blocks)
        threading.Thread(target=transcribe_and_type, args=(audio,), daemon=True).start()
    _blocks, _silence = [], 0

def _audio_cb(indata, frames, t, status):
    global current_rms, _blocks, _silence
    blk = indata[:, 0].copy()
    rms = float(np.sqrt(np.mean(blk ** 2)))
    current_rms = rms if recording else 0.0
    if not recording:
        return
    _blocks.append(blk)
    _silence = _silence + 1 if rms < SILENCE_TH else 0
    if _silence >= SILENCE_BLK or len(_blocks) >= MAX_BLOCKS:
        _flush()

def cancel_and_stop():
    global recording, cancelled
    cancelled = True
    recording = False

def _stop_flush():
    time.sleep(0.5)
    if not cancelled:
        _flush()
    else:
        global _blocks, _silence
        _blocks, _silence = [], 0
    overlay.hide()
    print("Остановлено.", flush=True)

def on_press(key):
    global recording, cancelled, _blocks, _silence
    if key == keyboard.Key.ctrl_r:
        if not recording:
            _blocks, _silence = [], 0
            cancelled = False
            recording = True
            overlay.show()
        else:
            cancelled = False
            recording = False
            threading.Thread(target=_stop_flush, daemon=True).start()
    elif key == keyboard.Key.esc:
        if recording:
            cancel_and_stop()
            threading.Thread(target=_stop_flush, daemon=True).start()

def hotkey_thread():
    with keyboard.Listener(on_press=on_press) as l:
        l.join()

def make_tray_icon():
    """Нарисовать иконку: оранжевый микрофон на тёмном фоне."""
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # Тёмный круг
    d.ellipse([2, 2, 62, 62], fill="#1e1e35")
    # Микрофон — тело
    d.rounded_rectangle([22, 8, 42, 38], radius=10, fill="#e05a00")
    # Подставка
    d.arc([14, 24, 50, 50], start=0, end=180, fill="#e05a00", width=3)
    d.line([32, 50, 32, 58], fill="#e05a00", width=3)
    d.line([24, 58, 40, 58], fill="#e05a00", width=3)
    return img

# ── Автозагрузка ─────────────────────────────────────────────────────────────
REG_RUN = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "VoiceType"

def is_autostart() -> bool:
    import winreg
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN)
        winreg.QueryValueEx(key, APP_NAME)
        winreg.CloseKey(key)
        return True
    except FileNotFoundError:
        return False

def set_autostart(enable: bool):
    import winreg
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN, 0, winreg.KEY_SET_VALUE)
    if enable:
        exe = sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__)
        # Если .py — запускать через pythonw чтобы не было консоли
        if not getattr(sys, "frozen", False):
            exe = f'"{sys.executable}" "{os.path.abspath(__file__)}"'
        else:
            exe = f'"{exe}"'
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, exe)
    else:
        try:
            winreg.DeleteValue(key, APP_NAME)
        except FileNotFoundError:
            pass
    winreg.CloseKey(key)

def toggle_autostart(icon, item):
    set_autostart(not is_autostart())
    icon.update_menu()

def quit_app(icon, item):
    global recording, cancelled
    cancelled = True
    recording = False
    icon.stop()
    overlay.root.after(0, overlay.root.destroy)

def tray_thread():
    icon_img = make_tray_icon()
    menu = pystray.Menu(
        pystray.MenuItem("VoiceType", None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(
            "Запускать с Windows",
            toggle_autostart,
            checked=lambda item: is_autostart()
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Закрыть", quit_app),
    )
    tray = pystray.Icon("VoiceType", icon_img, "VoiceType", menu)
    tray.run()

threading.Thread(target=hotkey_thread, daemon=True).start()
threading.Thread(target=tray_thread, daemon=True).start()

# Поток микрофона всегда открыт — нет задержки при старте записи
_mic_stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                              blocksize=BLOCKSIZE, dtype="float32",
                              callback=_audio_cb)
_mic_stream.start()

overlay.run()
