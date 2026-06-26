import ctypes
import sys
ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-monitor DPI aware
mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "Global\\MarsVoiceAssistant")
if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
    sys.exit(0)

# Imports
from pystray import Icon, Menu, MenuItem
from PIL import Image
import threading
import os
import queue
import tkinter as tk
import time
from pygame import mixer
from gtts import gTTS
import tempfile
import psutil
import pygame
import subprocess
from pydualsense import pydualsense



DUALSENSE_VENDOR_ID = 0x54C
DUALSENSE_PRODUCT_IDS = [0xCE6, 0xDF2] 
STEAM_PATH = r"D:\Programs\Steam\steam.exe"
log_queue = queue.Queue()
tts_queue = queue.Queue()
tts_volume = 1.0 


def queue_add(q, item):
    if q.full():
        q.get()  # remove oldest item
        q.put(item)
    else:
        q.put(item)

def _check_dualsense_combo():
    result = [False]
    def _check():
        try:
            ds = pydualsense()
            ds.init()
            result[0] = False
            ds.close()
        except:
            result[0] = False

    t = threading.Thread(target=_check)
    t.start()
    t.join(timeout=1.0)  # give it 1 second max
    return result[0]
    

def _controller_worker():
    
    pygame.joystick.quit()
    pygame.joystick.init()
    was_connected = queue.Queue(3)
    was_connected.put(True)
    was_connected.put(True)
    was_connected.put(False)

    while True:
        print(list(was_connected.queue))
        pygame.joystick.quit()
        pygame.joystick.init()
        connected = pygame.joystick.get_count() > 0
        print("Controllers: ", pygame.joystick.get_count())

        if _steam_running():
            print("Steam already running")
            time.sleep(1)
            continue

        if connected and True not in list(was_connected.queue):
            
            print(" Controller connected!")
            _launch_steam_bigpicture()
       
        elif _check_dualsense_combo():
           print(" DualSense combo detected!")
           _launch_steam_bigpicture()

        queue_add(was_connected, connected)
        time.sleep(1)

def _steam_running():
    return any(p.name().lower() == "steam.exe" for p in psutil.process_iter(["name"]))

def _launch_steam_bigpicture():
    if _steam_running():
        print("[Controller] Steam already running, skipping launch")
        return
    print("[Controller] Launching Steam Big Picture")
    speak("Launching Steam")
    subprocess.Popen([STEAM_PATH, "-bigpicture"])

def playAudio(fname, volume):
    mixer.init()
    mixer.music.load(fname)
    mixer.music.set_volume(volume)
    mixer.music.play()
    while mixer.music.get_busy():
        time.sleep(0.01)
    mixer.music.stop()
    mixer.music.unload()

def _tts_worker():
    
    while True:
        item = tts_queue.get()
        if item is None:  # poison pill
            break

        text, volume = item
        fname = None
        try:
            # Generate MP3
            tts = gTTS(text, lang="en")
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                fname = f.name
            tts.save(fname)

            # Play
            playAudio(fname, volume)

        except Exception as e:
            print(f"[TTS Error] {e}")
        finally:
            mixer.music.stop()
            mixer.music.unload()
            if fname and os.path.exists(fname):
                os.remove(fname)
            tts_queue.task_done()


def speak(text, volume="default"):
    global tts_volume

    if not text:
        return
    
    print(f"[TTS] {text}")

    # Name pronunciation fixes
    text = text.replace("aman", "Aa men")
    text = text.replace("Aman", "Aa men")
    text = text.replace("AMAN", "Aa men")

    vol = tts_volume if volume == "default" else volume

    
    tts_queue.put((text, vol))


class FakeConsole:
    def __init__(self, q): self.q = q
    def write(self, text): self.q.put(text)
    def flush(self): pass

# --- Tray icon ---
def build_tray(root):
    def show(icon, item): root.after(0, root.deiconify)
    def hide(icon, item): root.after(0, root.withdraw)
    def quit_app(icon, item):
        icon.stop()
        root.after(0, root.destroy)

    icon_image = Image.open("assets/icon.ico")
    menu = Menu(
        MenuItem("Show Console", show),
        MenuItem("Hide Console", hide),
        MenuItem("Quit", quit_app),
    )
    return Icon("Mars: Voice Assistant", icon_image, "Mars", menu)



def app_logic():
    playAudio("assets/startup.mp3", 1.0)
    print("Mars Initialized!")

    while True:
        time.sleep(2)





def main():

    def poll():
        while not log_queue.empty():
            msg = log_queue.get_nowait()
            text.configure(state="normal")
            text.insert("end", msg)
            text.see("end")
            text.configure(state="disabled")
        root.after(100, poll)

    root = tk.Tk()
    root.title("Mars: Terminal")
    root.geometry("650x400")

    text = tk.Text(root, state="disabled", bg="black", fg="lime",
                                      font=("Consolas", 10))
    text.pack(fill="both", expand=True)

    
    sys.stdout = FakeConsole(log_queue)
    sys.stderr = FakeConsole(log_queue)

    
    root.protocol("WM_DELETE_WINDOW", root.withdraw)

    


    # Start tray in background thread
    icon = build_tray(root)
    threading.Thread(target=app_logic, daemon=True).start()
    threading.Thread(target=icon.run, daemon=True).start()
    threading.Thread(target=_tts_worker, daemon=True).start()
    threading.Thread(target=_controller_worker, daemon=True).start()

    # Hidden on startup
    root.withdraw()

    poll()
    root.mainloop()

if __name__ == "__main__":
    main()




