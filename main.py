# Imports

import comtypes
import ctypes
from ctypes import cast,POINTER
import sys
ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-monitor DPI aware
mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "Global\\MarsVoiceAssistant") 
if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS (To keep only one instance running)
    sys.exit(0)

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
from vosk import Model, KaldiRecognizer
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
import pyautogui as g
import pyaudio as au


# Audio settings and setup
FRAMES_PER_BUFFER = 3200
FORMAT = au.paInt16
CHANNELS = 1
RATE = 16000
stream = None
p = None
mic_ready = threading.Event()

IGNORED_INPUT_DEVICES = [
    "Microsoft Sound Mapper",
    "Primary Sound Capture Driver",
    "Primary Sound Driver",
]

IGNORED_OUTPUT_DEVICES = [
    "Microsoft Sound Mapper",
    "Primary Sound Driver",
]

current_output_device = None
current_input_device = None

def get_input_devices():
    pa = au.PyAudio()
    devices = []
    for i in range(pa.get_device_count()):
        info = pa.get_device_info_by_index(i)
        if info["maxInputChannels"] > 0:
            name = info["name"]
            if any(ignored in name for ignored in IGNORED_INPUT_DEVICES):
                continue
            try:
                test = pa.open(format=FORMAT, channels=CHANNELS, rate=RATE,
                               input=True, input_device_index=i,
                               frames_per_buffer=FRAMES_PER_BUFFER)
                test.close()
                overlap = next((d for d in devices if name in d or d in name), None)
                if overlap is None:
                    devices.append(name)
                elif len(name) > len(overlap):  # new name is longer → replace
                    devices[devices.index(overlap)] = name
            except:
                pass
    pa.terminate()
    if devices:
        return devices
    else:
        print("No input devices found")
        return []

def input_device(device_name=None):
    global stream, p, current_input_device
    mic_ready.clear()
    try:
        if stream:
            stream.stop_stream()
            stream.close()
        if p:
            p.terminate()
    except Exception as e:
        print(f"[Microphone] Error closing stream: {e}")
    
    try:
        p = au.PyAudio()
        device_index = None
        if device_name:
            for i in range(p.get_device_count()):
                info = p.get_device_info_by_index(i)
                if (info["name"] in device_name or device_name in info["name"]) and info["maxInputChannels"] > 0:
                    device_index = i
                    break
        default = p.get_default_input_device_info()["name"]
        stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE,
                        input=True, input_device_index=device_index,
                        frames_per_buffer=FRAMES_PER_BUFFER)
        current_input_device = device_name or default
        print(f"[Microphone] Input device: {device_name or default + '(System Default)'}")
        mic_ready.set()
    except Exception as e:
        print(f"[Microphone] Error: {e}")



def get_output_devices():
    pa = au.PyAudio()
    devices = []
    for i in range(pa.get_device_count()):
        info = pa.get_device_info_by_index(i)
        if info["maxOutputChannels"] > 0:
            name = info["name"]
            if any(ignored in name for ignored in IGNORED_OUTPUT_DEVICES):
                continue
            try:
                test = pa.open(format=au.paFloat32, channels=1, rate=44100,
                               output=True, output_device_index=i,
                               frames_per_buffer=512)
                test.close()
                overlap = next((d for d in devices if name in d or d in name), None)
                if overlap is None:
                    devices.append(name)
                elif len(name) > len(overlap):  # new name is longer → replace
                    devices[devices.index(overlap)] = name
            except:
                pass
    pa.terminate()

    if devices:
        return devices
    else:
        print("No output devices found.")
        return []
    
def output_device(device_name=None):
    p = au.PyAudio()
    global current_output_device
    try:
        mixer.music.stop()
        mixer.quit()
    except Exception as e:
        print(f"[Audio] Error stopping mixer: {e}")
        print("[Audio] Reinitializing mixer...")
        mixer.init()
        print("[Audio] Mixer reinitialized with default output device.")
    try:
        mixer.init(devicename=device_name)
    except Exception as e:
        print(f"[Audio] Error initializing mixer: {e}")
    default = p.get_default_output_device_info()["name"]
    current_output_device = device_name or default
    print(f"[Audio] Output device: {device_name or default + '(System Default)'}")

    

# Controller IDs
DUALSENSE_VENDOR_ID = 0x54C
DUALSENSE_PRODUCT_IDS = [0xCE6, 0xDF2] 

# Paths
STEAM_PATH = r"D:\Programs\Steam\steam.exe"
MODEL_PATH = r"D:\Useful\Speech Model\vosk-model-small-en-us-0.15"

# Other Variables
log_queue = queue.Queue()
tts_queue = queue.Queue()
tts_volume = 1.0 

# Vosk setup
model = None
recognizer = None
model_ready = threading.Event()

def _load_models():
    global model, recognizer
    print("[Vosk] Loading model...")
    model = Model(MODEL_PATH)
    recognizer = KaldiRecognizer(model, RATE)
    print("[Vosk] Model ready!")
    model_ready.set()  


vol_dict = {'volume': 'number', 0: -65.25, 1: -55.9, 2: -50.9, 3: -47.1, 4: -44.1, 5: -41.6, 6: -39.4, 7: -37.6, 
            8: -35.9, 9: -34.4, 10: -33.0, 11: -31.7, 12: -30.6, 13: -29.5, 14: -28.5, 15: -27.5, 16: -26.6, 17: -25.8,
              18: -25.0, 19: -24.2, 20: -23.5, 21: -22.8, 22: -22.2, 23: -21.5, 24: -20.9, 25: -20.3, 26: -19.8, 27: -19.2, 
              28: -18.7, 29: -18.2, 30: -17.7, 31: -17.2, 32: -16.8, 33: -16.3, 34: -15.9, 35: -15.5, 36: -15.1, 37: -14.7, 
              38: -14.3, 39: -13.9, 40: -13.5, 41: -13.2, 42: -12.8, 43: -12.5, 44: -12.1, 45: -11.8, 46: -11.5, 47: -11.2, 
              48: -10.9, 49: -10.6, 50: -10.3, 51: -10.0, 52: -9.7, 53: -9.4, 54: -9.1, 55: -8.8, 56: -8.6, 57: -8.3, 58: -8.1, 
              59: -7.8, 60: -7.6, 61: -7.3, 62: -7.1, 63: -6.8, 64: -6.6, 65: -6.4, 66: -6.1, 67: -5.9, 68: -5.7, 69: -5.5, 70: -5.3, 
              71: -5.1, 72: -4.9, 73: -4.6, 74: -4.4, 75: -4.2, 76: -4.0, 77: -3.9, 78: -3.7, 79: -3.5, 80: -3.3, 81: -3.1, 82: -2.9, 
              83: -2.7, 84: -2.6, 85: -2.4, 86: -2.2, 87: -2.0, 88: -1.9, 89: -1.7, 90: -1.5, 91: -1.4, 92: -1.2, 93: -1.0, 94: -0.9, 
              95: -0.7, 96: -0.6, 97: -0.4, 98: -0.3, 99: -0.1,100:0.0}

num_dict_ones = {"zero":0,"one":1,"two":2,"three":3,"four":4,"five":5,"six":6,"seven":7,"eight":8,"nine":9,
            "eleven":11,"twelve":12,"thirteen":13,"fourteen":14,"fifteen":15,"sixteen":16,"seventeen":17,
            "eighteen":18,"nineteen":19}

num_dict_tens = {"twenty":20,"thirty":30,"forty":40,"fifty":50,"sixty":60,"seventy":70,"eighty":80,"ninety":90,}

def convertToNum(sentence):
    
    tens = 0
    ones = 0
    sentence2 = sentence.split()

    finished_sentence=""
    next=True
    
    for i in range(0,len(sentence2)):
        if next==False:
            next=True
            continue
        
        if sentence2[i] in num_dict_tens or sentence2[i] in num_dict_ones:
            if sentence2[i] in num_dict_tens:
                tens = num_dict_tens[sentence2[i]]
                try:
                    a = sentence2[i+1]
                except: 
                    final_num = tens
                    finished_sentence+=str(final_num)+" "
                    continue
                if len(sentence2)>1 and sentence2[i+1] in num_dict_ones:
                    ones = num_dict_ones[sentence2[i+1]]
                    final_num = tens+ones
                    finished_sentence+=str(final_num)+" "
                    next=False
                    
                else:
                    final_num = tens
                    finished_sentence+=str(final_num)+" "
            else:
                ones = num_dict_ones[sentence2[i]]
                final_num = ones
                finished_sentence+=str(final_num)+" "
        else:
            finished_sentence+=sentence2[i]+" "

    return finished_sentence


def DeviceVolume(mode,num=0,app=None):
    comtypes.CoInitialize()
    try:
        devices = AudioUtilities.GetSpeakers()
        volume = cast(devices.EndpointVolume,POINTER(IAudioEndpointVolume))
        if mode.lower() =='set':
            volume.SetMasterVolumeLevel(vol_dict[num],None)
            g.press("volumeup")
            g.press("volumedown")
        elif mode.lower() == 'get':
            g.press("volumeup")
            g.press("volumedown")
            return int(volume.GetMasterVolumeLevelScalar()*100)
        else:
            print("Invalid mode. Use 'set' or 'get'.")
            
    finally:
        comtypes.CoUninitialize()

def queue_add(q, item):
    if q.full():
        q.get()  # remove oldest item
        q.put(item)
    else:
        q.put(item)

def _check_dualsense():
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
    print("Controllers: ", pygame.joystick.get_count())
    was_connected = queue.Queue(3)
    was_connected.put(True)
    was_connected.put(True)
    was_connected.put(False)

    while True:
        
        pygame.joystick.quit()
        pygame.joystick.init()
        connected = pygame.joystick.get_count() > 0
        

        if _steam_running():
            print("Steam already running")
            time.sleep(1)
            continue

        if connected and True not in list(was_connected.queue):
            print("Controllers: ", pygame.joystick.get_count())
            print(" Controller connected!")
            _launch_steam_bigpicture()
       
        elif _check_dualsense():
           pass

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
    mixer.init()
    


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
    threading.Thread(target=_load_models, daemon=True).start()
    threading.Thread(target=load_microphone, daemon=True).start()
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




