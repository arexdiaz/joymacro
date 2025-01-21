from evdev import InputDevice, ecodes, list_devices
import asyncio
import logging
import threading

class EVDevice:
    def __init__(self, dev_name):
        self.stop = False
        self.device = InputDevice(self.get_device(dev_name))
        self.held_buttons = 0

    def key_lstnr(self, event):
        """
        Intercept and block volume keys from being processed by the system.
        """
        if event.type == ecodes.EV_KEY:
            if event.code == ecodes.KEY_VOLUMEUP and event.value == 1:
                return event.code
            elif event.code == ecodes.KEY_VOLUMEDOWN and event.value == 1:
                return event.code
            if event.code == ecodes.KEY_VOLUMEUP and event.value == 0:
                return 0
            elif event.code == ecodes.KEY_VOLUMEDOWN and event.value == 0:
                return 0

    def get_device(self, name):
        devices = [InputDevice(path) for path in list_devices()]

        for device in devices:
            if device.name.lower() == name.lower():
                return device.path

def list_input_devices(devices):
    """ TODO: Fix later
    List all input devices to help identify the correct one to monitor.
    """
    for device in devices:
        print(f"{device.path}: {device.name}")
