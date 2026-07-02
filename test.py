# Imports
from cProfile import label
import pickle
import json
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
        return ["Default Output"] + devices
    else:
        print("No output devices found.")
        return []













def output_device(device_name=None):
    


    global current_output_device
    speaker_ready.clear()
    if get_output_devices() == []:
        print("[Audio] No output devices found.")
        current_output_device = None
        speaker_ready.set()
        return
    else:
        mixer.init()

    print(f"[Audio] Setting output device: {device_name or 'System Default'}")
    p = au.PyAudio()
    try:
        mixer.music.stop()
        mixer.quit()
    except Exception as e:
        print(f"[Audio] Error stopping mixer: {e}")
    try:
        mixer.init(devicename=device_name)
    except Exception as e:
        print(f"[Audio] Error initializing mixer: {e}")
    default = p.get_default_output_device_info()["name"]
    p.terminate()
    current_output_device = device_name or default
    print(f"[Audio] Output device: {device_name or default + '(System Default)'}")
    







print("Setting output device...")
while True:
    print("Loop")
    try:
        print("before 1")
        output_device()
        print("before 2")
        mixer.music.load("assets/sounds/hotkey.wav")
        mixer.music.play()
        time.sleep(2)
        print("yes")
    except Exception as e:
        print(e)
        print("no")
        time.sleep(5)