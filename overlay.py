from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget
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

    def killWindow(self):
        if not self.last_active:
            logger.error("No active window found")
            return
        name, pid = self.last_active
        if "Desktop" in name:
            return
        self.exec(f"kill {pid}")
        self.toggleVisibility()

    def spawnLogout(self):
        power_cmd = "qdbus org.kde.LogoutPrompt /LogoutPrompt org.kde.LogoutPrompt.promptShutDown"
        self.exec(power_cmd)
        self.toggleVisibility()

    def getServiceStatus(self, service):
        status = self.exec(f"systemctl is-active --quiet {service}")
        return status.returncode == 0

    def toggleService(self, service):
        button = self.sender()
        label, status = button.text().split(":")
        service_status = self.getServiceStatus(service)
        action = "stop" if service_status else "start"

        self.exec(f"systemctl {action} {service}")

        button_state, button_color = ["OFF", self.gs.gray] if service_status else \
                                     ["ON", self.gs.green]

        button.setText(f"{label}: {button_state}")
        button.setStyleSheet(self.gs.buttonStyle(button_color, self.gs.button_font_size, self.gs.opacity))

    def checkDesktop(self):
        pid = self.exec("pkill plasmashell", status=True)
        if not pid:
            # threading.Thread(target=self.exec, args=(f"sudo -u pi plasmashell", False,)).start()
            self.exec("sudo -u pi plasmashell &", False)

    @pyqtSlot()
    def populateWindowsCont(self):
        """Loop to check for new windows and add them to the 'Windows' container."""
        self.cm.getContainer("Window Manager").resetLayout()
        windows = WindowManager().check_windows()
        for window in windows:
            if "plasma" in window["title"].lower(): continue
            self.cm.getContainer("Window Manager").createButton(
                window["title"], partial(self.exec, f"kill {window["pid"]}"),
                self.gs.gray, self.gs.opacity)
        self.cm.getContainer("Window Manager").populateContainer()
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
        
        self.createSubcontainer("Services", primary_container)
        self.createSubcontainer("Apps", primary_container)
        self.createSubcontainer("Scripts", primary_container)
        self.createSubcontainer("Window Manager", primary_container, pos="bottom")
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
            service_state, bg_color = ["ON", self.gs.green] if self.getServiceStatus(service) else ["OFF", self.gs.gray]
            self.cm.getContainer("Services").createButton(f"{label_text}: {service_state}", \
                                       partial(self.toggleService, service), \
                                       bg_color, self.gs.opacity)
        '''Script Stuff'''
        scripts = {
            "Tmux Session": "tmux new-session -d -s simple",
            "Link Cores": "/home/pi/scripts/link_cores.sh",
            "gov: placeholder": "echo hello"
        }
        for label_text, script in scripts.items():
            self.cm.getContainer("Scripts").createButton(label_text, partial(self.threadedExec, script))
        
        '''Apps Stuff'''                             
        apps = {
            "Konsole": "konsole",
            "Emulation Station": "es-de"
        }
        for label_text, app in apps.items():
            self.cm.getContainer("Apps").createButton(label_text, partial(self.launchApp, app), self.gs.gray, self.gs.opacity)

        '''Debug Stuff'''
        self.cm.getContainer("debug_menu").createButton("toggle_desktop", self.checkDesktop, self.gs.gray, self.gs.opacity)
        self.cm.getContainer("debug_menu").createButton("debug_exit", self.closeApplication, self.gs.red, 0.35)
        
        '''Primary Stuff'''
        brightness = self.exec("brightnessctl get").stdout.strip()
        self.cm.getContainer("Primary").createSlider(self.setBrightness, "Brightness", value=int(brightness), min=1, max=255, pos="top")
        self.cm.getContainer("Primary").createButton("Power Options", self.spawnLogout, self.gs.gray, self.gs.opacity, "bottom")
        
        '''Populate Menus'''
        self.cm.poulateAllContainers()