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

_LOG = os.path.join(os.path.expanduser("~"), "voicetype_debug.log")
def _log(msg):
    with open(_LOG, "a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%H:%M:%S')} {msg}\n")

DEFAULT_CACHE = "C:/gigaam_cache"
MODEL_NAME    = "v3_e2e_ctc"
SAMPLE_RATE   = 16000
BLOCKSIZE     = 1600
SILENCE_TH    = 0.004
SILENCE_BLK   = 15   # 1.5 сек тишины → сброс чанка
MAX_BLOCKS    = 150  # 15 сек максимум на чанк

# CPU torchaudio требует torchcodec которого нет — заменяем load на soundfile
import torchaudio as _torchaudio
import soundfile as _sf
import torch as _torch
def _sf_load(path, normalize=True, **kw):
    data, sr = _sf.read(str(path), dtype='float32', always_2d=True)
    return _torch.from_numpy(data.T), sr
_torchaudio.load = _sf_load

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

    CDN = "https://cdn.chatwm.opensmodel.sberdevices.ru/GigaAM"
    MODEL_FILES = [
        (f"{MODEL_NAME}.ckpt",            422 * 1024 * 1024),
        (f"{MODEL_NAME}_tokenizer.model",   1 * 1024 * 1024),
    ]

    def _purge_cache(cache):
        for fname, _ in MODEL_FILES:
            fp = os.path.join(cache, fname)
            if os.path.isfile(fp):
                try: os.unlink(fp)
                except Exception: pass

    def _download_file_direct(url, dest, total_bytes, on_progress):
        import urllib.request as ur
        tmp = dest + ".part"
        try:
            req = ur.Request(url, headers={"User-Agent": "VoiceType/1.0"})
            with ur.urlopen(req, timeout=60) as src, open(tmp, "wb") as out:
                downloaded = 0
                while True:
                    buf = src.read(65536)
                    if not buf:
                        break
                    out.write(buf)
                    downloaded += len(buf)
                    on_progress(downloaded, total_bytes)
        except Exception as e:
            if os.path.isfile(tmp):
                os.unlink(tmp)
            raise
        os.replace(tmp, dest)

    def _show_manual():
        import webbrowser
        status_var.set("Скачайте вручную и положите в C:/gigaam_cache")
        webbrowser.open(f"{CDN}/{MODEL_NAME}.ckpt")

    def download():
        btn_dl.config(state="disabled")
        btn_br.config(state="disabled")
        cache = DEFAULT_CACHE
        os.makedirs(cache, exist_ok=True)

        total_bytes = sum(b for _, b in MODEL_FILES)
        downloaded_so_far = [0]

        def on_progress(got, total_file):
            mb = (downloaded_so_far[0] + got) / 1024 / 1024
            frac = min((downloaded_so_far[0] + got) / total_bytes, 0.99)
            win.after(0, lambda f=frac, m=mb: (
                update_progress(f),
                status_var.set(f"Скачивание: {m:.0f} / ~423 МБ")
            ))

        def _do():
            _purge_cache(cache)
            for attempt in range(3):
                try:
                    for fname, fsize in MODEL_FILES:
                        dest = os.path.join(cache, fname)
                        if os.path.isfile(dest) and os.path.getsize(dest) >= fsize * 0.99:
                            downloaded_so_far[0] += fsize
                            continue
                        win.after(0, lambda n=fname:
                            status_var.set(f"Загрузка {n}…"))
                        _download_file_direct(
                            f"{CDN}/{fname}", dest, fsize, on_progress)
                        downloaded_so_far[0] += fsize

                    # Загрузить модель (проверит контрольную сумму)
                    _gigaam.load_model(MODEL_NAME, device="cpu", download_root=cache)
                    result["path"] = cache
                    win.after(0, lambda: update_progress(1.0))
                    win.after(500, win.destroy)
                    return

                except Exception as e:
                    err = str(e)
                    _purge_cache(cache)
                    downloaded_so_far[0] = 0
                    if attempt < 2:
                        win.after(0, lambda a=attempt, s=err[:40]:
                            status_var.set(f"Ошибка, повтор {a+2}/3… ({s})"))
                        time.sleep(3)
                    else:
                        win.after(0, lambda s=err[:60]:
                            status_var.set(f"Не удалось скачать: {s}"))
                        win.after(0, lambda: btn_dl.config(state="normal"))
                        win.after(0, lambda: btn_br.config(state="normal"))
                        win.after(0, lambda: btn_manual.pack(pady=(4, 0)))

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

    btn_manual = tk.Button(win, text="Открыть ссылку в браузере",
                           font=("Segoe UI", 9), relief="flat",
                           fg=ACC, bg=BG, activeforeground=WHITE,
                           activebackground=BG, cursor="hand2",
                           command=lambda: _show_manual())

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
try:
    model = _gigaam.load_model(MODEL_NAME, device="cpu", download_root=CACHE_DIR)
except AssertionError:
    # Модель повреждена — удалить и показать мастер повторно
    for _fname in (f"{MODEL_NAME}.ckpt", f"{MODEL_NAME}_tokenizer.model"):
        _fp = os.path.join(CACHE_DIR, _fname)
        if os.path.isfile(_fp):
            try:
                os.unlink(_fp)
            except Exception:
                pass
    CACHE_DIR = run_setup_wizard()
    model = _gigaam.load_model(MODEL_NAME, device="cpu", download_root=CACHE_DIR)
import torch as _torch_q
_torch_q.quantization.quantize_dynamic(model, {_torch_q.nn.Linear}, dtype=_torch_q.qint8, inplace=True)
print("Готово. Right Ctrl — начать запись.", flush=True)

recording       = False
cancelled       = False
current_rms     = 0.0
tr_lock         = threading.Lock()
_target_hwnd    = None   # окно, которое было активно при старте записи

import ctypes, ctypes.wintypes as _wt
_u32 = ctypes.WinDLL('user32', use_last_error=True)
_u32.GetForegroundWindow.restype                  = _wt.HWND
_u32.SetForegroundWindow.argtypes                 = [_wt.HWND]
_u32.SetForegroundWindow.restype                  = _wt.BOOL
_u32.BringWindowToTop.argtypes                    = [_wt.HWND]
_u32.BringWindowToTop.restype                     = _wt.BOOL
_u32.GetWindowThreadProcessId.argtypes            = [_wt.HWND, ctypes.POINTER(_wt.DWORD)]
_u32.GetWindowThreadProcessId.restype             = _wt.DWORD
_u32.AttachThreadInput.argtypes                   = [_wt.DWORD, _wt.DWORD, _wt.BOOL]
_u32.AttachThreadInput.restype                    = _wt.BOOL

def _send_unicode(text):
    """Отправить текст через SendInput + KEYEVENTF_UNICODE — не зависит от раскладки."""
    KEYEVENTF_UNICODE = 0x0004
    KEYEVENTF_KEYUP   = 0x0002

    class _KI(ctypes.Structure):
        _fields_ = [("wVk", _wt.WORD), ("wScan", _wt.WORD),
                    ("dwFlags", _wt.DWORD), ("time", _wt.DWORD),
                    ("dwExtraInfo", ctypes.c_size_t)]

    class _U(ctypes.Union):
        _fields_ = [("ki", _KI), ("_pad", ctypes.c_byte * 32)]

    class _INPUT(ctypes.Structure):
        _fields_ = [("type", _wt.DWORD), ("u", _U)]

    inputs = []
    for ch in text:
        cp = ord(ch)
        scans = [cp] if cp < 0x10000 else [0xD800 | ((cp - 0x10000) >> 10),
                                            0xDC00 | ((cp - 0x10000) & 0x3FF)]
        for sc in scans:
            for fl in (KEYEVENTF_UNICODE, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP):
                u = _U(); u.ki = _KI(0, sc, fl, 0, 0)
                inputs.append(_INPUT(1, u))

    arr = (_INPUT * len(inputs))(*inputs)
    _u32.SendInput(len(inputs), arr, ctypes.sizeof(_INPUT))


def _force_foreground(hwnd):
    """SetForegroundWindow надёжно работает только из foreground-треда — используем AttachThreadInput."""
    k32 = ctypes.WinDLL('kernel32', use_last_error=True)
    cur  = k32.GetCurrentThreadId()
    fg   = _u32.GetForegroundWindow()
    fg_t = _u32.GetWindowThreadProcessId(fg, None)
    if fg_t and fg_t != cur:
        _u32.AttachThreadInput(cur, fg_t, True)
        _u32.SetForegroundWindow(hwnd)
        _u32.BringWindowToTop(hwnd)
        _u32.AttachThreadInput(cur, fg_t, False)
    else:
        _u32.SetForegroundWindow(hwnd)

def paste_text(text):
    hwnd = _target_hwnd
    _log(f"paste hwnd={hwnd} fg={_u32.GetForegroundWindow()}")
    if hwnd:
        r = _force_foreground(hwnd)
        time.sleep(0.35)
        _log(f"after SetFG fg={_u32.GetForegroundWindow()} expected={hwnd}")
    _send_unicode(text + " ")
    _log(f"SendInput done for {text!r}")

NOISE_Y = re.compile(r'(?:^|(?<= ))[ыЫ](?=[а-яёА-ЯЁ])')


def clean(text):
    _EN_SHORT = {'ok', 'hi', 'no', 'yes', 'wow', 'the', 'and', 'or', 'but',
                 'in', 'on', 'at', 'to', 'for', 'lol', 'omg', 'bye'}

    def _filter_latin(m):
        w = m.group()
        if w.lower() in _EN_SHORT:
            return w
        vowels = sum(1 for c in w if c in 'aeiouAEIOU')
        if vowels >= 2 and len(w) >= 3:
            return w
        return ''
    text = re.sub(r'[a-zA-Z]+', _filter_latin, text).strip()

    text = NOISE_Y.sub('', text).strip()
    text = re.sub(r' {2,}', ' ', text)
    return text.strip()

def trim_end(audio, thr=SILENCE_TH * 0.4):
    rms = [np.sqrt(np.mean(audio[i:i+BLOCKSIZE]**2))
           for i in range(0, len(audio), BLOCKSIZE)]
    last = next((i for i,r in enumerate(reversed(rms)) if r >= thr), None)
    if last is None: return np.array([], dtype=np.float32)
    return audio[:(len(rms)-last)*BLOCKSIZE]


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
            raw  = result.text.strip()
            text = clean(raw)
            _log(f"raw={raw!r} clean={text!r} cancelled={cancelled} hwnd={_target_hwnd}")
            if text and not cancelled:
                print(f"-> {text}", flush=True)
                paste_text(text)
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
            global _target_hwnd
            _target_hwnd = _u32.GetForegroundWindow()
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
