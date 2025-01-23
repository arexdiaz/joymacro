from PyQt6.QtCore import QThread, pyqtSignal
from Xlib import X, display, Xatom, error
import subprocess, time
import logging


logger = logging.getLogger(__name__)

def _getPid(window_id):
    disp = display.Display()
    window = disp.create_resource_object("window", window_id)
    try:
        pid = window.get_full_property(disp.intern_atom("_NET_WM_PID"), Xatom.CARDINAL)
        return pid.value[0] if pid else None
    except error.BadWindow:
        logger.error(f"BadWindow error: Invalid window ID {window_id}")
        return None

def getWindows():
    try:
        result = subprocess.run(["wmctrl", "-lp"], capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"Error: {result.stderr}")
            return []
        
        windows = result.stdout.strip().split("\n")
        
        window_list = []
        for window in windows:
            parts = window.split(None, 3)
            if len(parts) == 4:
                window_id, desktop_id, machine, title = parts
                pid = _getPid(int(window_id, 16))

                if pid is None: continue

                result = subprocess.run(f"ps -p {pid} -o comm=", capture_output=True, shell=True, text=True)
                binary_name = result.stdout.strip() if result.returncode == 0 else "Unknown"
                
                window_list.append({
                    "window_id": window_id,
                    "desktop_id": desktop_id,
                    "machine": machine,
                    "title": title,
                    "pid": pid,
                    "binary_name": binary_name,
                })
        
        return window_list
        
    except Exception as e:
        logger.error(f"Error: {e}")
        return []

class WindowMonitorThread(QThread):
    new_window_detected = pyqtSignal(dict)
    window_closed = pyqtSignal(dict)

    def __init__(self, overlay):
        super().__init__()
        self.overlay = overlay
        self.running = True
        self.previous_windows = {}
        self.window_string = None

    def run(self):
        while self.running:
            current_windows = {window['pid']: window for window in getWindows()}

            for pid, window in current_windows.items():
                if pid not in self.previous_windows:
                    self.new_window_detected.emit(window)

            for pid, window in self.previous_windows.items():
                if pid not in current_windows:
                    self.window_closed.emit(window)
            self.previous_windows = current_windows
            self.msleep(1000)

    def stop(self):
        self.running = False
