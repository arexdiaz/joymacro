from functools import partial
from PyQt6.QtWidgets import QPushButton
from PyQt6.QtCore import QTime, QDate
import logging
import netifaces
import requests
import threading
import subprocess
import os
import psutil
import types
logger = logging.getLogger("main")


'''Commands go here'''
def exec(command):
    result = subprocess.run(command, capture_output=True, shell=True, text=True)
    logger.error(f"{command}: {result.stderr.strip()}") if result.returncode != 0 else None
    return result

def detachExec(string):
    command = [i for i in string.split(" ") if i]
    subprocess.Popen(
        command,
        shell=False,
        start_new_session=True,
        env=os.environ.copy()
    )

def get_private_ip(interface='wlp1s0'):
    try:
        addresses = netifaces.ifaddresses(interface)
        private_ip = addresses[netifaces.AF_INET][0]['addr']
    except (ValueError, KeyError, IndexError):
        private_ip = "N/A"
    return private_ip

def get_public_ip():
    try:
        response = requests.get('https://api.ipify.org?format=json')
        public_ip = response.json()['ip']
    except requests.RequestException:
        public_ip = "N/A"
    return public_ip

def get_essid(interface='wlp1s0'):
    try:
        result = subprocess.run(['iwgetid', interface, '--raw'], capture_output=True, text=True, check=True)
        essid = result.stdout.strip()
    except subprocess.CalledProcessError:
        essid = "N/A"
    return essid

def initStats(self, window):
    if not self.is_init:
        self.createLabel(f"ID: {window.id}\n" \
                            f"PID: {window.pid}\n" \
                            f"Title: {window.title}\n" \
                            f"Binary: {window.binary}\n" \
                            f"Is Minimized: {window.is_minimized}\n" \
                            f"Is Maximized: {window.is_maximized}\n" \
                            f"Is Fullscreen: {window.is_fullscreen}\n" \
                            f"Type: {window.get_fullscreen_type}\n" \
                            f"Is Active: {window.is_active}", "window_id_label", 16)
        self.removeWidget("empty")
        self.populateContainer()
        self.is_init = True

    self.parent.container.setVisible(False)
    self.container.setVisible(True)

def onWindowOpen(self, window):
    sub = self.createChildContainer(f"{window.title}", id=str(window.id))
    sub.createButton("Fullscreen", window.toggleFullscreen)
    sub.createButton("Maximize", window.toggleMaximize)
    sub.createButton("Minimize", window.toggleMinimize)
    sub.createButton("Close", window.close)
    stats = sub.createChildContainer("debug_info (WIP)", pos="bottom")
    stats.is_init = False
    stats.initStats = types.MethodType(initStats, stats)
    stats.populateContainer()
    sub.populateContainer()
    self.removeWidget("empty")
    self.populateContainer()
    button = sub.getWidget("debug_info_(wip)").widget()
    button.disconnect()
    button.clicked.connect(partial(stats.initStats, window))


def onWindowClose(self, window):
    id = str(window.id)
    child = self.getChild(id)
    widget = self.getWidget(id)

    self.removeWidget(id) if widget else logger.error(f"button: {id} not found")

    if not child:
        logger.error(f"child container: {id} not found")
        return

    if child.container.isVisible():
        child.container.setVisible(False)
        self.container.setVisible(True)

    self.removeChild(id)

def updateProfile(self):
    current_profile = exec("echo -n $(echo $(sudo /usr/sbin/nvpmodel -q) | awk 'END{print $NF}')").stdout.strip()
    for i in range(self.layout.count()):
        button = self.layout.itemAt(i).widget()
        if not isinstance(button, QPushButton):
            continue
        if button.text().endswith(self.check):
            button.setText(button.text().replace(self.check, ""))
        if button.text().split(":")[0] == current_profile:
            button.setText(f"{button.text()}{self.check}")

def changeProfile(self, name, value):
    self.current_profile = name
    cmd = exec(f"sudo /usr/sbin/nvpmodel -m {value}")
    self.updateProfile()

def getHWStatus(self):
    essid = get_essid()
    current_time = QTime.currentTime().toString("h:mm AP")
    current_date = QDate.currentDate().toString("MMM dd")
    if essid != self.essid:
        self.essid = essid
        self.private_ip = get_private_ip()
        self.public_ip = get_public_ip()

    host_name = os.uname().nodename
    user = os.getlogin()

    battery_percent = psutil.sensors_battery()
    if battery_percent.power_plugged:
        battery_status = " (Charging)"
    else:
        battery_status = ""

    index = exec("echo -n $(echo $(sudo /usr/sbin/nvpmodel -q) | awk 'END{print $NF}')").stdout.strip()
    profile_container = self.getChild("Toolbox").getChild("OC Profile")
    profile_container.current_profile = profile_container.profiles[index]
    self.getWidget("hwstat").widget().setText(
            f"{current_date} {current_time}\n"\
            f"{user}@{host_name}\n"\
            f"ip: {self.private_ip} pub: {self.public_ip}\n"\
            f"{profile_container.current_profile} {int(battery_percent.percent)}%{battery_status}"
        )