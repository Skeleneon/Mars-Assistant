# Imports
from cProfile import label
import pickle
import json
from pydoc import text
import random
import comtypes
import ctypes
from ctypes import cast,POINTER
import sys
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
import logging

ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-monitor DPI aware
mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "Global\\MarsVoiceAssistant") 
if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS (To keep only one instance running)
    sys.exit(0)

logging.basicConfig(
    filename="logs/mars_errors.log",
    level=logging.ERROR,
    format="%(asctime)s %(message)s"
)
def log_exception(exc_type, exc_value, exc_traceback):
    logging.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
sys.excepthook = log_exception




settings={}

# Controller IDs
DUALSENSE_VENDOR_ID = 0x54C
DUALSENSE_PRODUCT_IDS = [0xCE6, 0xDF2] 

# Paths
STEAM_PATH = r"D:\Programs\Steam\steam.exe"
MODEL_PATH = r"D:\Useful\Speech Model\vosk-model-small-en-us-0.15"

# Other Variables
tts_volume = 1.0 
current_output_device = None
current_input_device = None
speech=None

# Vosk setup
model = None
recognizer = None


# Audio settings and setup
FRAMES_PER_BUFFER = 3200
FORMAT = au.paInt16
CHANNELS = 1
RATE = 16000
stream = None
p = None

# Threading Events
mic_ready = threading.Event()
speaker_ready = threading.Event()    
model_ready = threading.Event()
settings_ready = threading.Event()
speaking=threading.Event()

# Queues
log_queue = queue.Queue()
tts_queue = queue.Queue()
audio_queue = queue.Queue()
text_queue = queue.Queue()


IGNORED_INPUT_DEVICES = [
    "Microsoft Sound Mapper",
    "Primary Sound Capture Driver",
    "Primary Sound Driver",
]

IGNORED_OUTPUT_DEVICES = [
    "Microsoft Sound Mapper",
    "Primary Sound Driver",
]

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


def get_input_devices(silent=False):
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
        return ["Default Input"] + devices
    else:
        if not silent:
            print("[Error] No input devices found")
        return []


def input_device(device_name=None):
    global stream, p, current_input_device
    print(f"[System] Setting input device: {device_name or 'System Default'}")
    mic_ready.clear()
    if device_name == "Default Input":
        device_name = None
    if get_input_devices() == []:
        current_input_device = None
        mic_ready.set()
        return
    try:
        if stream:
            stream.stop_stream()
            stream.close()
        if p:
            p.terminate()
    except Exception as e:
        print(f"[Error] while closing stream: {e}")
    
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
        
        print(f"[System] Input device set to: {device_name or default + '(System Default)'}")
        mic_ready.set()
    except Exception as e:
        print(f"[Error] while setting input device: {e}")
        current_input_device = None
        mic_ready.set()

def get_output_devices(silent=False):
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
        return ["Default Output"] + devices
    else:
        if not silent:
            print("[Error] No output devices found.")
        return []

def output_device(device_name=None):
    while not mic_ready.is_set():
        time.sleep(0.1)


    global current_output_device
    speaker_ready.clear()
    if device_name == "Default Output":
        device_name = None
    if get_output_devices() == []:
        current_output_device = None
        speaker_ready.set()
        return
    else:
        mixer.init()

    print(f"[System] Setting output device: {device_name or 'System Default'}")
    p = au.PyAudio()
    try:
        mixer.music.stop()
        mixer.quit()
    except Exception as e:
        print(f"[Error] while stopping mixer: {e}")
    try:
        mixer.init(devicename=device_name)
    except Exception as e:
        print(f"[Error] while initializing mixer: {e}")
    default = p.get_default_output_device_info()["name"]
    p.terminate()
    current_output_device = device_name or default
    print(f"[System] Output device: {device_name or default + '(System Default)'}")
    

    speaker_ready.set()

def _load_stuff():
    global tts_volume, current_input_device, current_output_device, speech
    global model, recognizer, settings
    settings=pickle.load(open("subfiles/settings.dat", "rb"))
    tts_volume = settings["tts_volume"]
    current_input_device = settings["input_device"]
    current_output_device = settings["output_device"]
    speech=settings["speech"]
    settings_ready.set()
    print("[System] Loading Vosk model...")
    model_ready.clear()
    model = Model(MODEL_PATH)
    recognizer = KaldiRecognizer(model, RATE)
    print("[System] Vosk Model ready!")
    model_ready.set()  




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
            print("[Error] Invalid mode. Use 'set' or 'get'.")
            
    finally:
        comtypes.CoUninitialize()



def mic_listen():
    while not mic_ready.is_set():
        time.sleep(0.1)


    global stream
    print("[System] Microphone Listening...")
    while True:
        mic_ready.wait() 
        if not speaking.is_set():
            try:
                chunk = stream.read(FRAMES_PER_BUFFER, exception_on_overflow=False)
                audio_queue.put(chunk)
            except Exception as e:
                print(f"[Error] while reading microphone: {e}")
                print("[Error] Exiting microphone listening thread...")
                time.sleep(2)
                break
        else:
            time.sleep(0.3)
            
def vosk_process():
    while not model_ready.is_set():
        time.sleep(0.1)
    global recognizer
    print("[System] Vosk processing started...")
    while True:
        
        chunk = audio_queue.get()
        if recognizer.AcceptWaveform(chunk):
            result = json.loads(recognizer.Result())
            if result.get("text"):
                print(f"[User] {result['text']}")
                text_queue.put(result['text'])
            
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
            print("[System] Steam already running!")
            time.sleep(1)
            continue

        if connected and True not in list(was_connected.queue):
            print("Controllers: ", pygame.joystick.get_count())
            print("[System] Controller connected!")
            _launch_steam_bigpicture()
       
        elif _check_dualsense():
           pass

        queue_add(was_connected, connected)
        time.sleep(1)

def _steam_running():
    return any(process.name().lower() == "steam.exe" for process in psutil.process_iter(["name"]))

def _launch_steam_bigpicture():
    if _steam_running():
        print("[System] Steam already running, skipping launch")
        return
    print("[System] Launching Steam Big Picture")
    if speech:
        speak("Launching Steam")
    else:
        playAudio("assets/sounds/hotkey.wav", 1.0)
    subprocess.Popen([STEAM_PATH, "-bigpicture"])

def playAudio(fname, volume):
    speaking.set()

    if current_output_device is None:
        speaking.clear()
        return
   
    mixer.music.load(fname)
    mixer.music.set_volume(volume)
    mixer.music.play()
    while mixer.music.get_busy():
        time.sleep(0.01)
    try:
        mixer.music.stop()
        mixer.music.unload()
    except:
        pass
    speaking.clear()
    

def _tts_worker():
   

    while not speaker_ready.is_set():
        time.sleep(0.1)
    
    print("[System] TTS worker started...")
    while True:
        
        

        item = tts_queue.get()
        if item is None:  # poison pill
            print("[System] TTS worker exiting...")
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
            print(f"[Error] while generating TTS: {e}")
        finally:
            try:
                mixer.music.stop()
                mixer.music.unload()
            except:
                pass
            if fname and os.path.exists(fname):
                os.remove(fname)
            tts_queue.task_done()

settings_window = None
def open_settings(root):
    global settings_window, current_input_device, current_output_device, tts_volume, speech

    

    # only one instance
    if settings_window and tk.Toplevel.winfo_exists(settings_window):
        settings_window.lift()
        return

    settings_window = tk.Toplevel(root)
    settings_window.title("Mars: Settings")
    settings_window.iconphoto(True, tk.PhotoImage(file="assets/icon.png"))
    settings_window.geometry("500x400")
    settings_window.configure(bg="#1a1a1a")
    settings_window.resizable(False, False)
    settings_window.update_idletasks()
    w = 500
    h = 450
    screen_w = settings_window.winfo_screenwidth()
    settings_window.geometry(f"{w}x{h}+{screen_w - w - 30}+20")

    def label(parent, text):
        tk.Label(parent, text=text, bg="#1a1a1a", fg="white",
                 font=("Consolas", 10)).pack(anchor="w", padx=20, pady=(10, 2))

    def separator():
        tk.Frame(settings_window, bg="#333333", height=1).pack(fill="x", padx=20, pady=5)

    no_output=False
    no_input=False

    
    # --- Input Device ---
    def refresh_input_menu():
        menu = input_menu["menu"]
        menu.delete(0, "end")
        for device in get_input_devices():
            menu.add_command(label=device, command=lambda d=device: input_var.set(d))

    def on_input_change(*args):
        threading.Thread(target=lambda: input_device(input_var.get()), daemon=True).start()

    input_frame = tk.Frame(settings_window, bg="#1a1a1a")
    input_frame.pack(fill="x")

    label(input_frame, "Input Device")
    input_var = tk.StringVar(value=current_input_device or "System Default")
    input_menu = tk.OptionMenu(input_frame, input_var, "")
    input_menu.configure(bg="#2a2a2a", fg="white", activebackground="#3a3a3a",
                            font=("Consolas", 10), highlightthickness=0)
    input_menu["menu"].configure(bg="#2a2a2a", fg="white")
    input_button = tk.Button(input_frame, command=None, text="None", bg="#1a1a1a", fg="white",
                 font=("Consolas", 10))

    


    if current_input_device is not None:
        
        input_menu.pack(fill="x", padx=20)
        input_menu["menu"].configure(postcommand=refresh_input_menu)
        input_var.trace_add("write", on_input_change)
    else:
        
        input_button.pack(anchor="w", fill="x", padx=20, pady=(10, 2))
        no_input=True
    
    
    separator()

    def refresh_output_menu():
        menu = output_menu["menu"]
        menu.delete(0, "end")
        for device in get_output_devices():
            menu.add_command(label=device, command=lambda d=device: output_var.set(d))

    def on_output_change(*args):
        threading.Thread(target=lambda: output_device(output_var.get()), daemon=True).start()

    output_frame = tk.Frame(settings_window, bg="#1a1a1a")
    output_frame.pack(fill="x")

    

    # --- Output Device ---
    label(output_frame, "Output Device")
    output_var = tk.StringVar(value=current_output_device or "System Default")
    output_menu = tk.OptionMenu(output_frame, output_var, "")
    output_menu.configure(bg="#2a2a2a", fg="white", activebackground="#3a3a3a",
                            font=("Consolas", 10), highlightthickness=0)
    output_menu["menu"].configure(bg="#2a2a2a", fg="white")
    output_button = tk.Button(output_frame, command=None, text="None", bg="#1a1a1a", fg="white",
                 font=("Consolas", 10))
    

    if current_output_device is not None:
        output_menu.pack(fill="x", padx=20)
        output_menu["menu"].configure(postcommand=refresh_output_menu)
        output_var.trace_add("write", on_output_change)

    else:
        
        output_button.pack(anchor="w", fill="x", padx=20, pady=(10, 2))
        no_output=True

    separator()

    def refresh_on_none():
        global current_input_device, current_output_device,mic_ready,speaker_ready
        mic_ready.clear()
        speaker_ready.clear()
        if current_input_device is None:
            threading.Thread(target=mic_listen, daemon=True).start()
       
        input_device()
        output_device()
        def _retry():

            input_device()
            if current_input_device is not None and current_output_device is not None:
                settings_window.after(0, _update_ui)

        def _update_ui():
            refresh_button.pack_forget()
            if input_button.winfo_manager() == "pack":
                input_button.pack_forget()
            if output_button.winfo_manager() == "pack":
                output_button.pack_forget()

            input_menu.pack(fill="x", padx=20)
            input_menu["menu"].configure(postcommand=refresh_input_menu)
            input_var.set(current_input_device)
            input_var.trace_add("write", on_input_change)

            output_menu.pack(fill="x", padx=20)
            output_menu["menu"].configure(postcommand=refresh_output_menu)
            output_var.set(current_output_device)
            output_var.trace_add("write", on_output_change)

        threading.Thread(target=_retry, daemon=True).start()

    separator()
    separator()
    #Refresh Button
    refresh_button = tk.Button(settings_window, command=refresh_on_none, text="Refresh Input & Output Devices", bg="#1a1a1a", fg="white",
                 font=("Consolas", 10))
    if no_input or no_output:
        refresh_button.pack(anchor="w", fill="x", padx=20, pady=(10, 2))

    # --- TTS Volume ---
    label(settings_window, "TTS Volume")
    volume_var = tk.DoubleVar(value=tts_volume)
    volume_slider = tk.Scale(settings_window, variable=volume_var, from_=0.0, to=1.0,
                             resolution=0.05, orient="horizontal", bg="#1a1a1a", fg="white",
                             troughcolor="#333333", highlightthickness=0, font=("Consolas", 9))
    volume_slider.pack(fill="x", padx=20)

    def on_volume_change(*args):
        global tts_volume
        tts_volume = volume_var.get()
        settings["tts_volume"] = tts_volume
    volume_var.trace_add("write", on_volume_change)

    separator()

   # --- Speech Toggle ---
    label(settings_window, "Speech")

    def toggle_switch(parent, initial=True, on_change=None):
        W, H = 56, 28
        canvas = tk.Canvas(parent, width=W, height=H, bg="#1a1a1a",
                           highlightthickness=0, cursor="hand2")
        state = [initial]

        def draw():
            canvas.delete("all")
            color = "#2196F3" if state[0] else "#555555"
            canvas.create_oval(0, 0, H, H, fill=color, outline="")
            canvas.create_oval(W-H, 0, W, H, fill=color, outline="")
            canvas.create_rectangle(H//2, 0, W-H//2, H, fill=color, outline="")
            pad = 3
            x = W - H + pad if state[0] else pad
            canvas.create_oval(x, pad, x+H-(pad*2), H-pad, fill="white", outline="")

        def toggle(event=None):
            state[0] = not state[0]
            draw()
            if on_change:
                on_change(state[0])

        canvas.bind("<Button-1>", toggle)
        draw()
        return canvas

    def on_speech_change(val):
        global speech
        speech = val

    toggle_switch(settings_window,
                  initial=settings.get("speech", True),
                  on_change=on_speech_change).pack(anchor="w", padx=20, pady=5)

def speak(text, volume="default"):
    global tts_volume
    
    
    if not text:
        return
    speaking.set()
    
    
    # Name pronunciation fixes
    text = text.replace("aman", "Aa men")
    text = text.replace("Aman", "Aa men")
    text = text.replace("AMAN", "Aa men")

    print(f"[Mars] {text}")

    if not speech:
        return

    vol = tts_volume if volume == "default" else volume

    
    tts_queue.put((text, vol))


class FakeConsole:
    def __init__(self, q): self.q = q
    def write(self, text): self.q.put(text)
    def flush(self): pass

# --- Tray icon ---
def build_tray(root):
    def show(icon, item): root.after(0, root.deiconify)
    def show_settings(icon, item): root.after(0, lambda: open_settings(root));show(icon, item)
    def quit_app(icon, item):
        settings["tts_volume"] = tts_volume
        settings["input_device"] = current_input_device
        settings["output_device"] = current_output_device
        settings["speech"] = speech
        with open("subfiles/settings.dat", "wb") as f:
            pickle.dump(settings, f)
        icon.stop()
        root.after(0, root.destroy)


    icon_image = Image.open("assets/icon.ico")
    menu = Menu(
        MenuItem("Show Console", show),
        MenuItem("Settings", show_settings),
        MenuItem("Quit", quit_app),
    )
    return Icon("Mars: Voice Assistant", icon_image, "Mars", menu)


def audio_manager():
    global current_input_device, current_output_device
    while not mic_ready.is_set() or not speaker_ready.is_set():
        time.sleep(0.1)
    while True:
        if get_input_devices(silent=True) == []:
            current_input_device = None
        if get_output_devices(silent=True) == []:
            current_output_device = None
        time.sleep(1)

def app_logic():
    

    while not model_ready.is_set() or not mic_ready.is_set() or not speaker_ready.is_set():
        time.sleep(0.1)

    if random.randint(1,5)==5:
        playAudio("assets/sounds/startup.wav", 1.0)
    else:
        playAudio("assets/sounds/startup.mp3", 1.0)
    speak("Mars Initialized!",0.2)
    print("[System] Mars Initialized!")

    while True:
        
        if text_queue.empty():
            time.sleep(0.5)
            continue

        text = text_queue.get()
        
        if text == "hello" :
            speak("Hello! How can I assist you today?")
        
        






def main():

    


    def poll():
        while not log_queue.empty():
            msg = log_queue.get_nowait()
            at_bottom = text.yview()[1] >= 0.99
            text.configure(state="normal")
            if msg.split():
                mode = msg.split()[0].lower()
            else:
                mode = "normal"

            match mode:
                case "[error]":
                    text.insert("end", msg, "error")
                case "[system]":
                    text.insert("end", msg, "system")
                case "[mars]":
                    text.insert("end", msg, "mars")
                case "[user]":
                    text.insert("end", msg, "user")
                case _:
                    text.insert("end", msg, "normal")

            if at_bottom:
                text.see("end")
            text.configure(state="disabled")
        root.after(100, poll)

    root = tk.Tk()
    root.title("Mars: Terminal")
    root.iconphoto(True, tk.PhotoImage(file="assets/icon.png"))

    root.geometry("650x450+30+20")
    
    
    

    text = tk.Text(root, state="disabled", bg="black", fg="lime",
                                      font=("Consolas", 10))
    
    text.pack(fill="both", expand=True)
    text.tag_configure("error", foreground="red")
    text.tag_configure("system", foreground="blue")
    text.tag_configure("mars", foreground="orange")
    text.tag_configure("user", foreground="yellow")
    text.tag_configure("normal", foreground="lime")
    

    
    sys.stdout = FakeConsole(log_queue)
    sys.stderr = FakeConsole(log_queue)

    
    root.protocol("WM_DELETE_WINDOW", root.withdraw)

    


    
    icon = build_tray(root)
    


    #initialization threads
    print("[System] Initializing...")
    threading.Thread(target=_load_stuff, daemon=True).start()
    while not settings_ready.is_set():
        time.sleep(0.1)

    threading.Thread(target=input_device, daemon=True).start()
    threading.Thread(target=output_device, daemon=True).start()

    #loop threads
   
    threading.Thread(target=mic_listen, daemon=True).start()
    threading.Thread(target=vosk_process, daemon=True).start()
    threading.Thread(target=app_logic, daemon=True).start()
    threading.Thread(target=icon.run, daemon=True).start()
    threading.Thread(target=_tts_worker, daemon=True).start()
    threading.Thread(target=_controller_worker, daemon=True).start()
    threading.Thread(target=audio_manager, daemon=True).start()

    # Hidden on startup
    root.withdraw()

    poll()
    root.mainloop()

if __name__ == "__main__":
    main()




