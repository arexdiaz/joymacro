from utils.sdl_devices import SDLDevices
import overlay as overlay_menu
import utils.ev_devices as ev_devices
import utils.log as log
import logging as _logging
import sdl2
import sdl2.ext
import subprocess
import time
import threading
import os


logging = log.setLogConfig("main")

class Osd:
    def __init__(self):
        self.process = subprocess.Popen(
            "osd_cat --pos=top --align=center --color=green --delay=1 --font='-*-helvetica-*-r-*-*-34-*-*-*-*-*-*-*' --shadow=4 -l 1",
            stdin=subprocess.PIPE,
            shell=True,
            text=True
        )

    def send_msg(self, msg):
        self.process.stdin.write(f"{msg}\n")
        self.process.stdin.flush()

class Mouse:
    def __init__(self):
        self.process = None

    def kill(self):
        if self.process:
            self.process.terminate()
            self.process.wait()
            self.process = None
    
    def start(self):
        self.process = subprocess.Popen("unclutter -idle 1 -root", shell=True)

class Main:
    def __init__(self):
        self.sdl_devices = SDLDevices()
        self.ev_gpio = ev_devices.EVDevice("gpio-keys")
        self.osd = Osd()

        self.states = None
        self.is_gpio_read = False
        self.is_joymouse = True
        self.btn_mapping = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17 ,18, 19]
        self.axis_mapping = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
        self.repeat = 0

    def macros(self):
        btn, axi, hat = self.states
        visib = {8, 7, 15}

        if btn == {8, 7, 15}:
            logging.debug("Toggling visibility")
            self.overlay.toggleVisibility()

        if self.is_joymouse and self.btn_mapping[4] in btn:
            logging.debug("Joymouse: OFF")
            self.osd.send_msg("Joymouse: OFF")
            self.is_joymouse = False
        elif not self.is_joymouse and self.btn_mapping[4] in btn:
            self.osd.send_msg("Joymouse: ON")
            logging.debug("Joymouse: ON")
            self.is_joymouse = True

    def loop(self):
        def read_sdl_events():
            prev_len_state = 0
            while True:
                for event in sdl2.ext.get_events():
                    self.states = self.sdl_devices.joy_lstnr(event)
                    len_state = sum(len(s) for s in self.states if isinstance(s, set))
                    if len_state > prev_len_state:
                        logging.debug(f"State: {self.states}")
                        self.macros()
                    prev_len_state = len_state

                time.sleep(0.2)

        threading.Thread(target=read_sdl_events).start()

        gs = overlay_menu.GlobalStyle()
        app = overlay_menu.QApplication([])
        self.overlay = overlay_menu.OverlayWindow(gs)
        app.exec()
        
if __name__ == "__main__":
    try:
        Main().loop()
    except KeyboardInterrupt:
        overlay_menu.QApplication.quit()
        os._exit(1)
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        os._exit(1)
