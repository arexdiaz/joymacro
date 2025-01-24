from PyQt6.QtCore import QThread, pyqtSignal
from Xlib import X, display, Xatom
import Xlib.error
import subprocess, time
import logging


logger = logging.getLogger(__name__)


def _getPid(window_id):
    disp = display.Display()
    window = disp.create_resource_object("window", window_id)
    try:
        pid = window.get_full_property(disp.intern_atom("_NET_WM_PID"), Xatom.CARDINAL)
        return pid.value[0] if pid else None
    except Xlib.error.BadWindow:
        return None

def getWindows():
    try:
        window_list = {}
        command = subprocess.run("wmctrl -l", capture_output=True, shell=True, text=True)
        if command.returncode != 0: return None

        windows = command.stdout.strip().split("\n")
        if len(windows) == 0: return None
        
        for window in windows:
            parts = window.split(None, 3)
            if len(parts) == 4:
                window_id, desktop_id, machine, title = parts
                pid = _getPid(int(window_id, 16))

                if pid is None: continue
                if "Plasma" in title: continue
                
                result = subprocess.run(f"ps -p {pid} -o comm=", capture_output=True, shell=True, text=True)
                binary_name = result.stdout.strip() if result.returncode == 0 else "Unknown"
                
                window_list[pid] = {
                    "window_id": window_id,
                    "desktop_id": desktop_id,
                    "machine": machine,
                    "title": title,
                    "pid": pid,
                    "binary_name": binary_name,
                }
        
        return window_list
        
    except Exception as e:
        logger.error(f"Error: {e}")

class WindowMonitorThread(QThread):
    on_window_create = pyqtSignal(dict)
    on_window_close = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.running = True
        self.previous_windows = {}
        self.eep_time = 1000

    def run(self):
        while self.running:
            self.current_windows = getWindows()
            if self.current_windows is None or self.current_windows == self.previous_windows:
                self.msleep(self.eep_time)
                continue

            for pid, window in self.current_windows.items():
                if pid not in self.previous_windows:
                    self.on_window_create.emit(window)

            for pid, window in self.previous_windows.items():
                if pid not in self.current_windows:
                    self.on_window_close.emit(window)
            self.previous_windows = self.current_windows
            self.msleep(self.eep_time)

    def stop(self):
        self.running = False
