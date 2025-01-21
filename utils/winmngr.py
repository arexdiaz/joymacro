import subprocess
from Xlib import X, display, Xatom

class WindowManager():
    def __init__(self):
        self.window_string = None

    def get_pid(self, window_id):
        disp = display.Display()
        window = disp.create_resource_object("window", window_id)
        pid = window.get_full_property(disp.intern_atom("_NET_WM_PID"), Xatom.CARDINAL)
        if pid:
            return pid.value[0]
        return None

    def get_opened_windows(self, result):
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
                    pid = self.get_pid(int(window_id, 16))

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
            print(f"Exception occurred: {e}")

    def print_windows(self):
        for window in self.window_list:
            print(f"Window ID: {window["window_id"]}, Title: {window["title"]}")
        print(f"Number of windows: {len(self.window_list)}")

    def check_windows(self):
            result = subprocess.run("wmctrl -l", capture_output=True, shell=True, text=True)
            if result.returncode != 0:
                return None
            if result.stdout.strip() != self.window_string:
                return self.get_opened_windows(result)
            return None
            