
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

FRAMES_PER_BUFFER = 3200
FORMAT = au.paInt16
CHANNELS = 1
RATE = 16000
stream = None
p = None
mic_ready = threading.Event()

current_output_device = None
current_input_device = None



IGNORED_OUTPUT_DEVICES = [
    "Microsoft Sound Mapper",
    "Primary Sound Driver",
]
IGNORED_INPUT_DEVICES = [
    "Microsoft Sound Mapper",
    "Primary Sound Capture Driver",
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


DeviceVolume('set', 25)
print("ok")