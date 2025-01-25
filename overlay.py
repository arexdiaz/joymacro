from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QPushButton, QLabel
from PyQt6.QtCore import Qt, QMetaObject, QThread, pyqtSignal, QTimer, pyqtSlot
from PyQt6 import sip
from functools import partial
from utils.container import ContainerManager, ContainerProp
from utils.winmngr import WindowMonitorThread
import logging
import threading
import subprocess
import os
import psutil

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
        self.is_active.emit()
        self.msleep(1000)

class OverlayWindow(QMainWindow):
    def __init__(self, gs):
        super().__init__()
        self.gs = gs
        self.last_active = None
        self.initUI()

        self.monitor_thread = WindowMonitorThread()
        self.monitor_thread.on_window_create.connect(self.addWindow)
        self.monitor_thread.on_window_close.connect(self.removeWindow)
        self.monitor_thread.start()

    def initUI(self):
        self.flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(self.flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        screen_size = QApplication.primaryScreen().size()
        self.setGeometry(0, 0, screen_size.width(), screen_size.height())
        self.setWindowState(Qt.WindowState.WindowFullScreen)

        self.cm = ContainerManager()

        self.menu_width = int(self.width() * 0.3)

        background_widget = QWidget(self)
        background_widget.setStyleSheet(f"background-color: {self.gs.bg_color};")
        background_widget.setGeometry(0, 0, self.width(), self.height())
        background_widget.mousePressEvent = self.toggleVisibility
        self.initMenu()

    def toggleVisibility(self, event=None):
        if self.isVisible():
            self.last_active = None
            self.cm.toggleContainers()
            self.hide()
            self.setWindowFlags(self.flags | Qt.WindowType.WindowTransparentForInput)
            QApplication.processEvents()
        else:
            self.getHWStatus()
            self.updateProfile()
            self.raise_()
            self.activateWindow()
            self.setWindowFlags(self.flags)
            self.setWindowState(Qt.WindowState.WindowFullScreen)
            self.show()
            QApplication.processEvents()

    def closeApplication(self, event=None):
        QApplication.quit()
        os._exit(0)

    '''Commands go here'''
    def exec(self, command):
        result = subprocess.run(command, capture_output=True, shell=True, text=True)
        logger.error(f"{command}: {result.stderr.strip()}") if result.returncode != 0 else None
        return result

    def threadedExec(self, command):
        threading.Thread(target=self.exec, args=(command,)).start()

    def launchApp(self, name):
        self.threadedExec(name)
        if self.isVisible():
            self.toggleVisibility()

    def setBrightness(self):
        sender = self.sender()
        self.exec(f"brightnessctl --quiet set {sender.value()}")

    def spawnLogout(self):
        power_cmd = "qdbus org.kde.LogoutPrompt /LogoutPrompt org.kde.LogoutPrompt.promptShutDown"
        self.exec(power_cmd)
        if self.isVisible():
            self.toggleVisibility()

    def toggleService(self, service):
        button = self.sender()
        label, status = button.text().split(":")
        service_status = self.exec(f"systemctl is-active --quiet {service}").returncode == 0
        action = "stop" if service_status else "start"

        self.exec(f"systemctl {action} {service}")

        button_state, button_color = ["OFF", self.gs.gray] if service_status else \
                                     ["ON", self.gs.green]

        button.setText(f"{label}: {button_state}")
        button.setStyleSheet(self.gs.buttonStyle(button_color, self.gs.button_font_size, self.gs.opacity))

    def toggleDesktop(self):
        pid = self.exec("pkill plasmashell", status=True)
        if not pid.returncode == 0:
            # threading.Thread(target=self.exec, args=(f"sudo -u pi plasmashell", False,)).start()
            self.exec("sudo -u pi plasmashell &", False)

    def addWindow(self, window):
        container = self.cm.getContainer(self.wm_name)
        container.createButton(window["binary_name"], partial(self.exec, f"kill {window["pid"]}"),
                               self.gs.gray, self.gs.opacity)
        container.removeWidget("empty")
        container.populateContainer()
    
    def removeWindow(self, window):
        container = self.cm.getContainer(self.wm_name)
        container.removeWidget(window["binary_name"].lower().replace(" ", "_"))
        container.removeWidget("empty")
        container.populateContainer()

    @pyqtSlot()
    def populateWindowsCont(self):
        container = self.cm.getContainer(self.wm_name)
        container.resetLayout()
        self.monitor_threads = []

        for pid, window in self.monitor_thread.current_windows.items():
            if "plasma" in window["title"].lower():
                continue

            container.createButton(window["binary_name"], partial(self.exec, f"kill {window["pid"]}"),
                self.gs.gray, self.gs.opacity)

        container.populateContainer()

    def updateProfile(self):
        current_profile = self.exec("echo -n $(echo $(sudo /usr/sbin/nvpmodel -q) | awk 'END{print $NF}')").stdout.strip()
        container = self.cm.getContainer(self.nvpm_name)
        for i in range(container.layout.count()):
            button = container.layout.itemAt(i).widget()
            if not isinstance(button, QPushButton):
                continue
            if button.text().endswith(self.profile_append):
                button.setText(button.text().replace(self.profile_append, ""))
            if button.text().split(":")[0] == current_profile:
                button.setText(f"{button.text()}{self.profile_append}")

    def changeProfile(self, name, value):
        cmd = f"sudo /usr/sbin/nvpmodel -m {value}"
        self.current_profile = name
        self.exec(cmd)
        self.updateProfile()

    def getHWStatus(self):
        host_name = self.exec("hostname").stdout.strip()
        local_ip_obj = self.exec("hostname -I")
        local_ip = local_ip_obj.stdout.strip().split(" ")[0] if local_ip_obj.returncode == 0 else "N/A"
        public_ip_obj = self.exec("curl -s4 --max-time 1 ifconfig.me")
        public_ip = public_ip_obj.stdout.strip() if public_ip_obj.returncode == 0 else "N/A"
        user = self.exec("whoami").stdout.strip()

        battery_percent = psutil.sensors_battery()
        if battery_percent.secsleft == psutil.POWER_TIME_UNLIMITED:
            time_left = "Charging"
        elif battery_percent.secsleft == psutil.POWER_TIME_UNKNOWN:
            time_left = "8"
        else:
            hours, remainder = divmod(battery_percent.secsleft, 3600)
            minutes, _ = divmod(remainder, 60)
            time_left = f"{(hours*-1)}h"

        self.cm.getContainer("Primary").getWidget("hwstat").widget().setText(
                f"{user}@{host_name}\n"\
                f"ip: {local_ip} | pub: {public_ip}\n"\
                f"{self.current_profile} | {int(battery_percent.percent)}% ({time_left})"
            )

    def getCPUStatus(self):
        cpu_usage = psutil.cpu_percent(percpu=True)
        cpu_status = []
        for i, usage in enumerate(cpu_usage):
            cpu_status.append(f"CPU{i}: {usage}%")
        for container in self.cm.containers.values():
            container.getWidget("cpu_stats").widget().setText(" ".join(cpu_status))
    
    def isAppActive(self):
        is_active = QApplication.activeWindow() == self
        if not is_active and self.isVisible():
            self.raise_()
            self.activateWindow()
        
    '''End Commands'''


    '''Init Thingy'''
    def createSubcontainer(self, label, prim_con, pos="top"):
        con = ContainerProp(self.height(), self.width(), self.gs)
        con.createContainer(self, self.width() - self.menu_width, 0, self.menu_width, \
                                           self.height(), self.gs.menu_color, visible=False)
        con.createLabel(f"{label}", "header", 28)
        con.createLabel(" ", "separator", 4, solid=True)
        con.createSubmenu(prim_con, "Back", self.gs.gray, self.gs.opacity)
        prim_con.createSubmenu(con, label, self.gs.gray, self.gs.opacity, pos)

        self.cm.addContainer(label, con)

    def initMenu(self):
        primary_container = ContainerProp(self.height(), self.width(), self.gs)
        primary_container.createContainer(self, self.width() - self.menu_width, 0, self.menu_width, \
                                           self.height(), self.gs.menu_color)
        self.cm.addContainer("Primary", primary_container)
        
        primary = self.cm.getContainer("Primary")
        primary.createLabel("Da Overlay Menu", "title", 28)
        primary.createLabel(" ", "hwstat", 16)
        primary.createLabel(" ", "separator", 4, solid=True)
        
        self.app_name = "Apps"
        self.toolbox_name = "Toolbox"
        self.services_name = "Services"
        self.wm_name = "Window Manager"
        self.debug_name = "debug_menu"
        self.createSubcontainer(self.app_name, primary_container)
        self.createSubcontainer(self.toolbox_name, primary_container)
        self.createSubcontainer(self.services_name, self.cm.getContainer(self.toolbox_name))
        self.createSubcontainer(self.wm_name, primary_container, pos="bottom")
        if logger.getEffectiveLevel() == logging.DEBUG:
            self.createSubcontainer("debug_menu", primary_container)
            self.cm.getContainer("debug_menu").createButton("toggle_desktop", self.toggleDesktop, self.gs.gray, self.gs.opacity)
            self.cm.getContainer("debug_menu").createButton("debug_exit", self.closeApplication, self.gs.red, 0.35)
        

        '''Services Stuff'''
        services = {
            "FTP": "vsftpd",
            "SecureShell": "ssh.socket",
            "Samba Share": "smbd"
        }

        for label_text, service in services.items():
            service_exist = self.exec(f"systemctl show {service} --no-page --property=LoadState")
            if service_exist.stdout.strip() == "LoadState=not-found":
                continue
            status = self.exec(f"systemctl is-active --quiet {service}").returncode == 0
            service_state, bg_color = ["ON", self.gs.green] if status else ["OFF", self.gs.gray]
            self.cm.getContainer(self.services_name).createButton(f"{label_text}: {service_state}", \
                                       partial(self.toggleService, service), \
                                       bg_color, self.gs.opacity)
                                       
                                       
        '''Script Stuff'''
        self.nvpm_name = "OC Profile"
        self.createSubcontainer(self.nvpm_name, self.cm.getContainer(self.toolbox_name))
        profile_value = self.exec("echo -n $(echo $(sudo /usr/sbin/nvpmodel -q) | awk 'END{print $NF}')").stdout.strip()
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
            self.cm.getContainer(self.nvpm_name).createButton(title, partial(self.changeProfile, name, value))


        scripts = {
            "Tmux Session": "tmux new-session -d -s simple",
            "Link Cores": "/home/pi/scripts/link_cores.sh",
            "Update Overlay": "cd /home/pi/overlay && git pull"
        }
        
        for label_text, script in scripts.items():
            self.cm.getContainer(self.toolbox_name).createButton(label_text, partial(self.threadedExec, script))


        '''Apps Stuff'''                             
        apps = {
            "Emulation Station": "es-de",
            "Konsole": "konsole",
        }
        for label_text, app in apps.items():
            self.cm.getContainer(self.app_name).createButton(label_text, partial(self.launchApp, app), self.gs.gray, self.gs.opacity)

        '''Primary Stuff'''
        brightness = self.exec("brightnessctl get").stdout.strip()
        primary.createSlider(self.setBrightness, "Brightness", value=int(brightness), min=1, max=255, pos="top")
        primary.createButton("Power Options", self.spawnLogout, self.gs.gray, self.gs.opacity, "bottom")
        
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