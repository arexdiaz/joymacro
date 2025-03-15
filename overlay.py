from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from functools import partial
from utils.container import ContainerManager, ContainerProp
import logging
import os
import utils.commands as cmd
import utils.window
import types

logger = logging.getLogger("main")

class GlobalStyle():
    def __init__(self):
        self.none = "0,0,0"
        self.red = "153,0,0"
        self.gray = "119,119,119"
        self.green = "0,255,0"
        self.button_font_size = "16"
        self.button_font_color = "white"
        self.elements_height = 50
        self.menu_color = "rgba(0, 0, 0, 200)"
        self.bg_color = "rgba(0, 0, 0, 150)"
        self.opacity = 0.15

    def buttonStyle(self, bg_color, font_size, opacity):
        return f"""
            QPushButton {{
                background-color: rgba({bg_color}, {opacity});
                color: white;
                font-size: {font_size}px;
                border: none;
                border-bottom: 2px solid gray;
                border-radius: 0px;
            }}

            QPushButton:hover {{
                background-color: rgba(255, 255, 255, 0.1);  /* Light transparent overlay on hover */
            }}

            QPushButton:pressed {{
                background-color: rgba(255, 255, 255, 0.2);  /* Slightly darker overlay when pressed */
            }}
        """

class StatusThread(QThread):
    battery_updated = pyqtSignal()

    def run(self):
        while True:
            self.battery_updated.emit()
            self.msleep(5000)

class CPUThread(QThread):
    cpu_updated = pyqtSignal()

    def run(self):
        while True:
            self.cpu_updated.emit()
            self.msleep(2500)

class AppThread(QThread):
    is_active = pyqtSignal()

    def run(self):
        while True:
            self.is_active.emit()
            self.msleep(250)

class OverlayWindow(QMainWindow):
    def __init__(self, gs):
        super().__init__()
        self.gs = gs
        self.initUI()

    def initUI(self):
        self.setWindowTitle("da_overlay")
        self.flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(self.flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        screen_size = QApplication.primaryScreen().size()
        self.setGeometry(QApplication.primaryScreen().geometry())
        
        self.cm = ContainerManager()

        self.menu_width = int(self.width() * 0.3)

        background_widget = QWidget(self)
        background_widget.setStyleSheet(f"background-color: {self.gs.bg_color};")
        background_widget.setGeometry(0, 0, self.width(), self.height())
        background_widget.mousePressEvent = self.toggleVisibility
        self.initMenu()

    def toggleVisibility(self, event=None):
        if self.isVisible():
            self.cm.toggleContainers()
            self.hide()
            self.setWindowFlags(self.flags | Qt.WindowType.WindowTransparentForInput)
            QApplication.processEvents()
        else:
            self.cm.getContainer(self.pc_name).getHWStatus()
            self.profile_container.updateProfile()
            self.setWindowFlags(self.flags)
            self.show()
            QApplication.processEvents()

    def closeApplication(self, event=None):
        QApplication.quit()
        os._exit(0)

    '''Commands go here'''
    def spawnLogout(self):
        line = "qdbus org.kde.LogoutPrompt /LogoutPrompt org.kde.LogoutPrompt.promptShutDown"
        cmd.exec(line)
        if self.isVisible():
            self.toggleVisibility()

    def setBrightness(self):
        sender = self.sender()
        cmd.exec(f"brightnessctl --quiet set {sender.value()}")

    def toggleService(self, service):
        button = self.sender()
        label, status = button.text().split(":")
        service_status = cmd.exec(f"systemctl is-active --quiet {service}").returncode == 0
        action = "stop" if service_status else "start"

        cmd.exec(f"systemctl {action} {service}")

        button_state, button_color = ["OFF", self.gs.gray] if service_status else \
                                     ["ON", self.gs.green]

        button.setText(f"{label}: {button_state}")
        button.setStyleSheet(self.gs.buttonStyle(button_color, self.gs.button_font_size, self.gs.opacity))
    
    def isAppActive(self):
        is_active = QApplication.activeWindow() == self
        if not is_active and self.isVisible():
            self.raise_()
            self.activateWindow()
        
    '''End Commands'''


    '''Init Thingy'''
    def initMenu(self):
        self.pc_name = "Primary Container"
        pc = ContainerProp(self.height(), self.width(), self.gs, label=self.pc_name)
        pc.createContainer(self, self.width() - self.menu_width, 0, self.menu_width, \
                                           self.height(), self.gs.menu_color)
        
        app_name = "App Launcher"
        toolbox_name = "Toolbox"
        nvpm_name = "OC Profile"
        services_name = "Services"
        wm_name = "Active Windows"
        debug_name = "debug_menu"

        primary_container = self.cm.addContainer(pc)
        primary_container.essid = None
        primary_container.public_ip = "N/A"
        primary_container.private_ip = "N/A"
        primary_container.createLabel("Da Overlay Menu", "title", 28)
        primary_container.createLabel(" ", "hwstat", 16)
        primary_container.createLabel(" ", "separator", 4, solid=True)
        primary_container.createButton("Power Options", self.spawnLogout, self.gs.gray, self.gs.opacity, pos="bottom")

        primary_container.getHWStatus = types.MethodType(cmd.getHWStatus, primary_container)

        winman_container = self.cm.addContainer(primary_container.createChildContainer(wm_name))
        winman_container.onWindowOpen = types.MethodType(cmd.onWindowOpen, winman_container)
        winman_container.onWindowClose = types.MethodType(cmd.onWindowClose, winman_container)

        window_monitor = utils.window.WindowMonitor()
        window_monitor.on_window_create.connect(winman_container.onWindowOpen)
        window_monitor.on_window_close.connect(winman_container.onWindowClose)
        window_monitor.start()

        launcher_container = self.cm.addContainer(primary_container.createChildContainer(app_name))
        toolbox_container  = self.cm.addContainer(primary_container.createChildContainer(toolbox_name, pos="bottom"))

        self.profile_container = self.cm.addContainer(toolbox_container.createChildContainer(nvpm_name))
        self.profile_container.updateProfile = types.MethodType(cmd.updateProfile, self.profile_container)
        self.profile_container.changeProfile = types.MethodType(cmd.changeProfile, self.profile_container)
        
        services_container = self.cm.addContainer(toolbox_container.createChildContainer(services_name))

        if logger.getEffectiveLevel() == logging.DEBUG:
            debug_container = self.cm.addContainer(primary_container.createChildContainer(debug_name))
            debug_container.createButton("debug_exit", self.closeApplication, self.gs.red, 0.35)

        '''Services Stuff'''
        services = {
            "FTP": "vsftpd",
            "SecureShell": "ssh.socket",
            "Samba Share": "smbd",
            "Bluetooth": "bluetooth.service",
            "WiFi": "wpa_supplicant.service",
        }

        for label_text, service in services.items():
            service_exist = cmd.exec(f"systemctl show {service} --no-page --property=LoadState")
            if service_exist.stdout.strip() == "LoadState=not-found":
                continue
            status = cmd.exec(f"systemctl is-active --quiet {service}").returncode == 0
            service_state, bg_color = ["ON", self.gs.green] if status else ["OFF", self.gs.gray]
            services_container.createButton(f"{label_text}: {service_state}", \
                                       partial(self.toggleService, service), \
                                       bg_color, self.gs.opacity)


        '''Script Stuff'''
        profile_value = cmd.exec("echo -n $(echo $(sudo /usr/sbin/nvpmodel -q) | awk 'END{print $NF}')").stdout.strip()
        self.profile_container.check = " ✓"
        self.profile_container.profiles = {
            "0": "Console",
            "1": "Handheld",
            "2": "OC CPU",
            "3": "OC GPU",
            "4": "OC All",
            "5": "Perf All",
            "6": "Perf OC All"
        }
        for value, name in self.profile_container.profiles.items():
            title = f"{value}: {name}"
            if value == profile_value:
                title += self.profile_container.check
                self.profile_container.current_profile = name
            self.profile_container.createButton(title, partial(self.profile_container.changeProfile, name, value))


        scripts = {
            "Tmux Session": partial(cmd.detachExec, "tmux new-session -d -s simple"),
            "Link Cores": partial(cmd.detachExec, "/home/pi/scripts/link_cores.sh"),
            "Update Overlay": partial(cmd.detachExec, "cd /home/pi/overlay && git fetch && git pull"),
            "Restart Joycond (WIP)": partial(logger.info, "this is a test!")
        }

        for label_text, script in scripts.items():
            toolbox_container.createButton(label_text, script)

        '''Apps Stuff'''                             
        apps = {
            "Emulation Station": "es-de",
            "Konsole": "konsole",
        }
        for label_text, app in apps.items():
           launcher_container.createButton(label_text, partial(cmd.detachExec, app))

        # Slider is absolute last
        primary_container.createSlider(
            self.setBrightness,
            "Brightness",
            value=int(cmd.exec("brightnessctl get").stdout.strip()), # TODO: This can be an emiter cause by an event in x11
            min=1, max=255,
            pos="top"
        )

        '''Populate Menus'''
        self.cm.poulateAllContainers()

        self.battery_thread = StatusThread()
        self.battery_thread.battery_updated.connect(primary_container.getHWStatus)
        self.battery_thread.start()

        self.cpu_thread = CPUThread()
        self.cpu_thread.cpu_updated.connect(self.cm._getCPUStatus)
        self.cpu_thread.start()

        self.is_active = AppThread()
        self.is_active.is_active.connect(self.isAppActive)
        self.is_active.start()
