from PyQt6.QtCore import QThread, pyqtSignal
from Xlib import X, display, Xatom
import subprocess, time
import logging


logger = logging.getLogger(__name__)

def _getDetails(result):
    def _getPid(window_id):
        disp = display.Display()
        window = disp.create_resource_object("window", window_id)
        pid = window.get_full_property(disp.intern_atom("_NET_WM_PID"), Xatom.CARDINAL)
        return pid.value[0] if pid else None

    try:
        if result.returncode != 0:
            print(f"Error: {result.stderr}")
            return []
        
        # Split the output into lines
        windows = result.stdout.strip().split("\n")
        
        # Parse the window information
        window_list = []
        for window in windows:
            parts = window.split(None, 3)
            if len(parts) == 4:
                window_id, desktop_id, machine, title = parts
                pid = _getPid(int(window_id, 16))

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

class WindowMonitorThread(QThread):
    new_window_detected = pyqtSignal(dict)
    window_closed = pyqtSignal(dict)

    def __init__(self, overlay):
        super().__init__()
        self.overlay = overlay
        self.running = True
        self.previous_windows = {}
        self.window_string = None
        self.eep_time = 1

    def getWindows(self):
        result = subprocess.run("wmctrl -l", capture_output=True, shell=True, text=True)
        if result.returncode != 0:
            return None
        if result.stdout.strip() != self.window_string:
            return _getDetails(result)
        return None

    def run(self):
        while self.running:
            self.overlay.windows = self.getWindows()
            if self.overlay.windows is None:
                time.sleep(self.eep_time)
                continue
            current_windows = {window['pid']: window for window in self.overlay.windows}
            # Check for new windows
            for pid, window in current_windows.items():
                if pid not in self.previous_windows:
                    self.new_window_detected.emit(window)
            # Check for closed windows
            for pid, window in self.previous_windows.items():
                if pid not in current_windows:
                    self.window_closed.emit(window)
            self.previous_windows = current_windows
            time.sleep(self.eep_time)

    def stop(self):
        self.running = False
