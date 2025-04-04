from functools import partial
from PyQt6.QtWidgets import QPushButton
from PyQt6.QtCore import QTime, QDate
from utils.commands import exec as cmd_exec
import logging
import netifaces
import requests
import threading
import subprocess
import os
import psutil
import types
import re

logger = logging.getLogger("main")


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

''' Profile Container Functions'''
def initProfile(self):
    profile_value = cmd_exec("echo -n $(echo $(sudo /usr/sbin/nvpmodel -q) | awk 'END{print $NF}')").stdout.strip()
    self.check = " ✓"
    exp = r"<\s*([^>]+?)\s*>"
    
    with open("/etc/nvpmodel.conf", "r") as f:
        lines = [line for line in re.findall(exp, f.read())
                if "POWER_MODEL" in line and "ID=" in line]

    self.profiles = [
        record
        for tokens in (line.strip().split() for line in lines)
        for record in [dict([("TYPE", tokens[0])] + [token.split("=", 1) for token in tokens[1:]])]
        if record.get("ID", "").isdigit()
    ]

    for p in self.profiles:
        title = f"{p.get("ID")}: {p.get("NAME")}"
        if id == profile_value:
            title += self.check
            self.current_profile = p.get("NAME")
        self.createButton(title, partial(self.changeProfile, p.get("NAME"), p.get("ID")))

def updateProfile(self):
    current_profile = cmd_exec("echo -n $(echo $(sudo /usr/sbin/nvpmodel -q) | awk 'END{print $NF}')").stdout.strip()
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
    cmd = cmd_exec(f"sudo /usr/sbin/nvpmodel -m {value}")
    self.updateProfile()

'''Status Container Functions'''
def initStats(stats, window):
    if not stats.is_init:
        stats_text = (
            f"ID: {window.id}\n"
            f"PID: {window.pid}\n"
            f"Title: {window.title}\n"
            f"Binary: {window.binary}\n"
            f"Is Minimized: {window.is_minimized}\n"
            f"Is Maximized: {window.is_maximized}\n"
            f"Is Fullscreen: {window.is_fullscreen}\n"
            f"Type: {window.get_fullscreen_type}\n"
            f"Is Active: {window.is_active}"
        )
        stats.createLabel(stats_text, "window_id_label", 16)
        stats.removeWidget("empty")
        stats.populateContainer()
        stats.is_init = True

    stats.parent.container.setVisible(False)
    stats.container.setVisible(True)

'''Window Manager Functions'''
def onWindowOpen(self, window):
    title = window.title if window.title.lower() != "unknown" else window.binary
    child_container = self.createChildContainer(title, id=str(window.id))
    actions = [
        ("Fullscreen", window.toggleFullscreen),
        ("Maximize", window.toggleMaximize),
        ("Minimize", window.toggleMinimize),
        ("Set Focus", window.setFocus),
        ("Close", window.close),
    ]
    extra_actions = [
        ("Keep Above Others", window.toggleAlwaysOnTop),
        ("No Tilebar and Frame (WIP)", window.toggleNoTitlebarFrame),
    ]
    for label, action in actions:
        child_container.createButton(label, action)

    extra_container = child_container.createChildContainer("More Actions", pos="bottom")
    for label, action in extra_actions:
        extra_container.createButton(label, action)
    extra_container.populateContainer()

    stats_container = child_container.createChildContainer("debug_info (WIP)", pos="bottom")
    stats_container.is_init = False
    stats_container.populateContainer()

    child_container.populateContainer()
    self.removeWidget("empty")
    self.populateContainer()

    debug_button = child_container.getWidget("debug_info_(wip)").widget()
    debug_button.disconnect()
    debug_button.clicked.connect(partial(initStats, stats_container, window))

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

'''Primary Container Functions'''
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

    i = cmd_exec("echo -n $(echo $(sudo /usr/sbin/nvpmodel -q) | awk 'END{print $NF}')").stdout.strip()
    profile_container = self.getChild("Toolbox").getChild("OC Profile")
    profile_container.current_profile = profile_container.profiles[int(i)].get("NAME")
    self.getWidget("hwstat").widget().setText(
            f"{current_date} {current_time}\n"\
            f"{user}@{host_name}\n"\
            f"ip: {self.private_ip} pub: {self.public_ip}\n"\
            f"{profile_container.current_profile} {int(battery_percent.percent)}%{battery_status}"
        )