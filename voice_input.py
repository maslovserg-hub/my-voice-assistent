import sys
import time
import ctypes
import speech_recognition as sr
import keyboard
import threading
import winsound
from pynput import keyboard as pynput_keyboard
try:
    import pyperclip
    has_pyperclip = True
except ImportError:
    has_pyperclip = False


def list_microphones():
    print("Доступные микрофоны:")
    for index, name in enumerate(sr.Microphone.list_microphone_names()):
        print(f"  {index}: {name}")


selected_mic_index = None
recording = False
stop_recording_event = threading.Event()
recording_thread = None
last_activate_time = 0.0


def play_start_signal():
    # Звуковой сигнал Windows перед началом записи
    winsound.Beep(1000, 180)


def get_foreground_window_title():
    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return ""
    length = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def set_clipboard_text(text: str):
    """Set text to clipboard using ctypes or pyperclip."""
    if has_pyperclip:
        try:
            pyperclip.copy(text)
            return True
        except Exception:
            pass
    CF_UNICODETEXT = 13
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    try:
        if not user32.OpenClipboard(None):
            return False
        user32.EmptyClipboard()
        data = text.encode('utf-16-le')
        h_global_mem = kernel32.GlobalAlloc(0x0002, len(data) + 2)
        if not h_global_mem:
            return False
        locked_mem = kernel32.GlobalLock(h_global_mem)
        if not locked_mem:
            return False
        ctypes.memmove(locked_mem, data, len(data))
        ctypes.memset(locked_mem + len(data), 0, 2)
        kernel32.GlobalUnlock(h_global_mem)
        user32.SetClipboardData(CF_UNICODETEXT, h_global_mem)
        return True
    finally:
        user32.CloseClipboard()


def paste_from_clipboard():
    """Paste text from clipboard using Ctrl+V."""
    time.sleep(0.1)
    keyboard.press('ctrl')
    time.sleep(0.05)
    keyboard.press('v')
    time.sleep(0.05)
    keyboard.release('v')
    time.sleep(0.05)
    keyboard.release('ctrl')
    time.sleep(0.1)


ULONG_PTR = ctypes.c_size_t


def release_all_modifiers():
    for key in ['ctrl', 'ctrl_l', 'ctrl_r', 'alt', 'alt_l', 'alt_r', 'shift', 'shift_l', 'shift_r', 'windows', 'win']:
        try:
            keyboard.release(key)
        except Exception:
            pass


def recognize_speech():
    global recording
    try:
        r = sr.Recognizer()
        r.dynamic_energy_threshold = True
        r.pause_threshold = 1.2
        r.non_speaking_duration = 0.6
        mic_args = {}
        if selected_mic_index is not None:
            mic_args['device_index'] = selected_mic_index
        with sr.Microphone(**mic_args) as source:
            print("Настраиваюсь на шум, пожалуйста, не говорите...")
            r.adjust_for_ambient_noise(source, duration=1)
            print("Начинаю запись... Нажмите правый Ctrl ещё раз для остановки")
            play_start_signal()
            partial_words = []

            while not stop_recording_event.is_set():
                try:
                    audio = r.listen(source, timeout=1, phrase_time_limit=2)
                except sr.WaitTimeoutError:
                    continue
                except Exception as e:
                    print(f"Ошибка прослушивания: {e}")
                    break

                try:
                    chunk = r.recognize_google(audio, language='ru-RU').strip()
                    if chunk:
                        partial_words.append(chunk)
                        current_text = " ".join(partial_words)
                        print("Промежуточно: " + current_text)
                        active_window = get_foreground_window_title()
                        print(f"Активное окно: {active_window}")
                        try:
                            release_all_modifiers()
                            time.sleep(0.05)
                            if set_clipboard_text(chunk + " "):
                                paste_from_clipboard()
                                print("Вставляю: " + chunk)
                            else:
                                raise OSError("Не удалось установить буфер обмена")
                        except Exception as e:
                            print(f"Ошибка вставки: {e}")
                            try:
                                keyboard.write(chunk + " ", delay=0.02)
                                print("Fallback: keyboard.write ввел: " + chunk)
                            except Exception as e2:
                                print(f"Fallback ошибка ввода текста: {e2}")
                except sr.UnknownValueError:
                    # Молчание или непонятная речь, продолжаем слушать
                    continue
                except sr.RequestError as e:
                    print("Ошибка сервиса: " + str(e))
                    break

            print("Останавливаю запись...")
            final_text = " ".join(partial_words).strip()
            if final_text:
                print("Распознано: " + final_text)
            else:
                print("Не удалось распознать речь")
    except Exception as e:
        print(f"Ошибка распознавания: {e}")
        recording = False
    finally:
        recording = False
        stop_recording_event.clear()


def on_activate():
    global recording, recording_thread, last_activate_time
    try:
        now = time.time()
        if now - last_activate_time < 0.5:
            return
        last_activate_time = now

        if not recording:
            recording = True
            stop_recording_event.clear()
            print("Горячая клавиша сработала, старт записи")
            recording_thread = threading.Thread(target=recognize_speech, daemon=True)
            recording_thread.start()
        else:
            print("Горячая клавиша сработала, остановка записи")
            stop_recording_event.set()
    except Exception as e:
        print(f"Ошибка в on_activate: {e}")


if __name__ == '__main__':
    if '--list-mics' in sys.argv:
        list_microphones()
        sys.exit(0)

    for index, arg in enumerate(sys.argv):
        if arg in ('--mic-id', '-m') and index + 1 < len(sys.argv):
            try:
                selected_mic_index = int(sys.argv[index + 1])
                print(f"Выбран микрофон {selected_mic_index}")
            except ValueError:
                print("Неверный индекс микрофона. Используйте целое число.")
                sys.exit(1)

    print("Запущен голосовой ввод. Нажмите правый Ctrl для старта и остановки записи")
    print("Текст будет печататься автоматически в активное поле по мере распознавания")
    print("Если микрофон слушает не тот, запустите скрипт с параметром --list-mics")

    # Используем pynput listener для точного определения правого Ctrl
    def on_release(key):
        try:
            if key == pynput_keyboard.Key.ctrl_r:
                on_activate()
        except Exception as e:
            print(f"Ошибка в on_release: {e}")

    try:
        with pynput_keyboard.Listener(on_release=on_release) as listener:
            listener.join()
    except Exception as e:
        print(f"Ошибка listener: {e}")