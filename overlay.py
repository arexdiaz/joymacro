from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QPushButton, QLabel
from PyQt6.QtCore import Qt, QMetaObject, QThread, pyqtSignal, QDate, QTime, pyqtSlot
from PyQt6 import sip
from functools import partial
from utils.container import ContainerManager, ContainerProp
import logging
import threading
import subprocess
import os
import psutil
import utils.commands as cmd
import utils.window


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

        self.pid = os.getpid()
        self.essid = None

        self.window_monitor = utils.window.WindowMonitor()
        self.window_monitor.on_window_create.connect(self.onWindowOpen)
        self.window_monitor.on_window_close.connect(self.onWindowClose)
        self.window_monitor.start()

        self.proc_black_list = [
            "polybar-mybar_DSI-0",
            "overlay_menu"
        ]

    def initUI(self):
        self.setWindowTitle("overlay_menu")
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
            self.getHWStatus()
            self.updateProfile()
            self.setWindowFlags(self.flags)
            self.show()
            QApplication.processEvents()

    def closeApplication(self, event=None):
        QApplication.quit()
        os._exit(0)

    '''Commands go here'''
    def setBrightness(self):
        sender = self.sender()
        cmd.exec(f"brightnessctl --quiet set {sender.value()}")

    def spawnLogout(self):
        power_cmd = "qdbus org.kde.LogoutPrompt /LogoutPrompt org.kde.LogoutPrompt.promptShutDown"
        cmd.exec(power_cmd)
        if self.isVisible():
            self.toggleVisibility()

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

    def toggleDesktop(self):
        pid = cmd.exec("pkill plasmashell", status=True)
        if not pid.returncode == 0:
            # threading.Thread(target=cmd.exec, args=(f"sudo -u pi plasmashell", False,)).start()
            cmd.exec("sudo -u pi plasmashell &", False)

    def killProc(self, window, force=False):
        window.close(1)
        proc_term = f"kill -9 {window.get_pid()}"
        sender = self.sender()
        
    def onWindowOpen(self, window):
        pid = window.pid
        name = window.title
        
        if name.lower() in self.proc_black_list:
            return
        
        # TODO: move container creation to winman_container
        sub = self.cm.addContainer(self.winman_container.createSubcontainer(f"{name}", id=str(pid)))
        sub.createButton("Fullscreen", window.toggleFullscreen)
        sub.createButton("Maximize", window.toggleMaximize)
        sub.createButton("Minimize (WIP)", window.toggleMinimize)
        sub.createButton("Close", window.close)
        sub.populateContainer()
        self.winman_container.removeWidget("empty")
        self.winman_container.populateContainer()
    
    def onWindowClose(self, window):
        id = str(window.pid)
        window_obj = self.cm.getContainer(id)

        if not window_obj:
            return

        if window_obj.container.isVisible():
            window_obj.container.setVisible(False)
            self.winman_container.container.setVisible(True)

        self.winman_container.removeWidget(id)
        self.cm.deleteContainer(id)

    def updateProfile(self):
        current_profile = cmd.exec("echo -n $(echo $(sudo /usr/sbin/nvpmodel -q) | awk 'END{print $NF}')").stdout.strip()
        for i in range(self.profile_container.layout.count()):
            button = self.profile_container.layout.itemAt(i).widget()
            if not isinstance(button, QPushButton):
                continue
            if button.text().endswith(self.profile_append):
                button.setText(button.text().replace(self.profile_append, ""))
            if button.text().split(":")[0] == current_profile:
                button.setText(f"{button.text()}{self.profile_append}")

    def changeProfile(self, name, value):
        cmd_str = f"sudo /usr/sbin/nvpmodel -m {value}"
        self.current_profile = name
        cmd.exec(cmd_str)
        self.updateProfile()

    def getHWStatus(self):
        essid = cmd.get_essid()
        current_time = QTime.currentTime().toString("h:mm AP")
        current_date = QDate.currentDate().toString("MMM dd")
        if essid != self.essid:
            self.essid = essid
            self.private_ip = cmd.get_private_ip()
            self.public_ip = cmd.get_public_ip()

        host_name = cmd.exec("hostname").stdout.strip()
        user = cmd.exec("whoami").stdout.strip()

        battery_percent = psutil.sensors_battery()
        if battery_percent.power_plugged:
            battery_status = " (Charging)"
        else:
            battery_status = ""

        self.cm.getContainer("primary_container").getWidget("hwstat").widget().setText(
                f"{current_date} {current_time}\n"\
                f"{user}@{host_name}\n"\
                f"ip: {self.private_ip} pub: {self.public_ip}\n"\
                f"{self.current_profile} {int(battery_percent.percent)}%{battery_status}"
            )

    def getCPUStatus(self):
        cpu_usage = psutil.cpu_percent(percpu=True)
        cpu_status = []
        for i, usage in enumerate(cpu_usage):
            cpu_status.append(f"CPU{i}: {usage}%")
        for container in self.cm.containers.values():
            try:
                container.getWidget("cpu_stats").widget().setText(" ".join(cpu_status))
            except KeyError:
                continue
    
    def isAppActive(self):
        is_active = QApplication.activeWindow() == self
        if not is_active and self.isVisible():
            self.raise_()
            self.activateWindow()
        
    '''End Commands'''


    '''Init Thingy'''
    def initMenu(self):
        pc = ContainerProp(self.height(), self.width(), self.gs, label="Primary Container")
        pc.createContainer(self, self.width() - self.menu_width, 0, self.menu_width, \
                                           self.height(), self.gs.menu_color)
        
        primary_container = self.cm.addContainer(pc)
        primary_container.createLabel("Da Overlay Menu", "title", 28)
        primary_container.createLabel(" ", "hwstat", 16)
        primary_container.createLabel(" ", "separator", 4, solid=True)
        
        app_name = "App Launcher"
        toolbox_name = "Toolbox"
        nvpm_name = "OC Profile"
        services_name = "Services"
        wm_name = "Active Windows"
        debug_name = "debug_menu"

        self.winman_container = self.cm.addContainer(primary_container.createSubcontainer(wm_name))
        launcher_container = self.cm.addContainer(primary_container.createSubcontainer(app_name))

        toolbox_container  = self.cm.addContainer(primary_container.createSubcontainer(toolbox_name, pos="bottom"))
        self.profile_container = self.cm.addContainer(toolbox_container.createSubcontainer(nvpm_name))
        services_container = self.cm.addContainer(toolbox_container.createSubcontainer(services_name))

        if logger.getEffectiveLevel() == logging.DEBUG:
            debug_container = self.cm.addContainer(primary_container.createSubcontainer(debug_name))
            debug_container.createButton("toggle_desktop", self.toggleDesktop, self.gs.gray, self.gs.opacity)
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
        self.profile_append = " ✓"
        self.profiles = {
            "0": "Console",
            "1": "Handheld",
            "2": "OC CPU",
            "3": "OC GPU",
            "4": "OC All",
            "5": "Perf All",
            "6": "Perf OC All"
        }
        for value, name in self.profiles.items():
            title = f"{value}: {name}"
            if value == profile_value:
                title += self.profile_append
                self.current_profile = name
            self.profile_container.createButton(title, partial(self.changeProfile, name, value))


        scripts = {
            "Tmux Session": "tmux new-session -d -s simple",
            "Link Cores": "/home/pi/scripts/link_cores.sh",
            "Update Overlay": "cd /home/pi/overlay && git fetch && git pull",
            "Restart Joycond (WIP)": "echo hello"
        }

        for label_text, script in scripts.items():
            toolbox_container.createButton(label_text, partial(cmd.detachExec, script))


        '''Apps Stuff'''                             
        apps = {
            "Emulation Station": "es-de",
            "Konsole": "konsole",
        }
        for label_text, app in apps.items():
           launcher_container.createButton(label_text, partial(cmd.detachExec, app))

        '''Primary Stuff'''
        brightness = cmd.exec("brightnessctl get").stdout.strip()
        primary_container.createSlider(self.setBrightness, "Brightness", value=int(brightness), min=1, max=255, pos="top")
        primary_container.createButton("Power Options", self.spawnLogout, self.gs.gray, self.gs.opacity, pos="bottom")
        
        for container in self.cm.containers.values():
            container.createLabel(" ", "cpu_stats", 12, pos="bottom")
    
        '''Populate Menus'''
        self.cm.poulateAllContainers()

        # Start the battery update thread
        self.battery_thread = StatusThread()
        self.battery_thread.battery_updated.connect(self.getHWStatus)
        self.battery_thread.start()

        self.cpu_thread = CPUThread()
        self.cpu_thread.cpu_updated.connect(self.getCPUStatus)
        self.cpu_thread.start()

        self.is_active = AppThread()
        self.is_active.is_active.connect(self.isAppActive)
        self.is_active.start()
