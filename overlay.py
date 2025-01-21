from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QPushButton
from PyQt5.QtCore import Qt, QRect, QThread, QMetaObject, pyqtSlot
from PyQt5.QtGui import QColor
from functools import partial
from utils.container import ContainerManager, ContainerProp
import logging
import threading
import subprocess
import os
from utils.winmngr import WindowManager
import time

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

class OverlayWindow(QMainWindow):
    def __init__(self, gs):
            super().__init__()
            self.gs = gs
            self.last_active = None
            self.initUI()

    def initUI(self):
        self.flags = Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint
        self.setWindowFlags(self.flags)
        self.setAttribute(Qt.WA_TranslucentBackground)
        screen_size = QApplication.primaryScreen().size()
        self.setGeometry(0, 0, screen_size.width(), screen_size.height())
        self.setWindowState(Qt.WindowFullScreen)

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
            self.setWindowFlags(self.flags | Qt.WindowTransparentForInput)
            QApplication.processEvents()
        else:
            self.updateProfile()
            QMetaObject.invokeMethod(self, "populateWindowsCont", Qt.QueuedConnection)
            self.raise_()
            self.activateWindow()
            self.setWindowFlags(self.flags)
            self.setWindowState(Qt.WindowFullScreen)
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

    def killWindow(self, title, pid):
        button = self.sender()
        self.exec(f"kill {pid}")
        self.cm.getContainer(self.wm_name).layout.removeWidget(button)
        button.deleteLater()

    def spawnLogout(self):
        power_cmd = "qdbus org.kde.LogoutPrompt /LogoutPrompt org.kde.LogoutPrompt.promptShutDown"
        self.exec(power_cmd)
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
        if not pid:
            # threading.Thread(target=self.exec, args=(f"sudo -u pi plasmashell", False,)).start()
            self.exec("sudo -u pi plasmashell &", False)

    @pyqtSlot()
    def populateWindowsCont(self):
        """Loop to check for new windows and add them to the 'Windows' container."""
        self.cm.getContainer(self.wm_name).resetLayout()
        windows = WindowManager().check_windows()
        for window in windows:
            if "plasma" in window["title"].lower(): continue
            self.cm.getContainer(self.wm_name).createButton(
                window["binary_name"], partial(self.killWindow, window["title"], window["pid"]),
                self.gs.gray, self.gs.opacity)
        self.cm.getContainer(self.wm_name).populateContainer()

    def updateProfile(self):
        current_profile = self.exec("echo -n $(echo $(sudo /usr/sbin/nvpmodel -q) | awk 'END{print $NF}')").stdout.strip()
        for i in range(self.cm.getContainer(self.nvpm_name).layout.count()):
            button = self.cm.getContainer(self.nvpm_name).layout.itemAt(i).widget()
            if not isinstance(button, QPushButton):
                continue
            if button.text().endswith(self.profile_append):
                button.setText(button.text().replace(self.profile_append, ""))
            if button.text().split(":")[0] == current_profile:
                button.setText(f"{button.text()}{self.profile_append}")

    def changeProfile(self, profile):
        cmd = f"sudo /usr/sbin/nvpmodel -m {profile}"
        self.exec(cmd)
        self.updateProfile()

    '''End Commands'''





    '''Init Thingy'''
    def createSubcontainer(self, label, prim_con, pos="top"):
        con = ContainerProp(self.height(), self.width(), self.gs)
        con.createContainer(self, self.width() - self.menu_width, 0, self.menu_width, \
                                           self.height(), self.gs.menu_color, visible=False)
        con.createSubmenu(prim_con, "Back", self.gs.gray, self.gs.opacity)
        prim_con.createSubmenu(con, label, self.gs.gray, self.gs.opacity, pos)

        self.cm.addContainer(label, con)

    def initMenu(self):
        primary_container = ContainerProp(self.height(), self.width(), self.gs)
        primary_container.createContainer(self, self.width() - self.menu_width, 0, self.menu_width, \
                                           self.height(), self.gs.menu_color)
        self.cm.addContainer("Primary", primary_container)
        
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
        current_profile = self.exec("echo -n $(echo $(sudo /usr/sbin/nvpmodel -q) | awk 'END{print $NF}')").stdout.strip()
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
            if value == current_profile:
                title += self.profile_append
            self.cm.getContainer(self.nvpm_name).createButton(title, partial(self.changeProfile, value))


        scripts = {
            "Tmux Session": "tmux new-session -d -s simple",
            "Link Cores": "/home/pi/scripts/link_cores.sh"
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


        '''Debug Stuff'''
        self.cm.getContainer("debug_menu").createButton("toggle_desktop", self.toggleDesktop, self.gs.gray, self.gs.opacity)
        self.cm.getContainer("debug_menu").createButton("debug_exit", self.closeApplication, self.gs.red, 0.35)
        

        '''Primary Stuff'''
        brightness = self.exec("brightnessctl get").stdout.strip()
        self.cm.getContainer("Primary").createSlider(self.setBrightness, "Brightness", value=int(brightness), min=1, max=255, pos="top")
        self.cm.getContainer("Primary").createButton("Power Options", self.spawnLogout, self.gs.gray, self.gs.opacity, "bottom")
        
        '''Populate Menus'''
        self.cm.poulateAllContainers()
