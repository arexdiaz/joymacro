import subprocess
import logging
import threading

logger = logging.getLogger("main")



'''Commands go here'''
def exec(command):
    result = subprocess.run(command, capture_output=True, shell=True, text=True)
    logger.error(f"{command}: {result.stderr.strip()}") if result.returncode != 0 else None
    return result

def threaded_exec(command):
    threading.Thread(target=exec, args=(command,)).start()

def set_brightness(sender):
    exec(f"brightnessctl --quiet set {sender.value()}")

def kill_window(last_active):
    if not last_active:
        logger.error("No active window found")
        return
    name, pid = last_active
    if "Desktop" in name:
        return
    exec(f"kill {pid}")

def get_service_status(service):
    status = exec(f"systemctl is-active --quiet {service}")
    return status.returncode == 0

def toggle_service_button(sender, service):
    label, status = sender.text().split(":")
    service_status = get_service_status(service)
    action = "stop" if service_status else "start"

    exec(f"systemctl {action} {service}")

    button_state, button_color = ["OFF", gs.gray] if service_status else \
                                    ["ON", gs.green]

    sender.setText(f"{label}: {button_state}")
    sender.setStyleSheet(gs.button_style(button_color, gs.button_font_size, gs.opacity))

def check_desktop():
    pid = exec("pkill plasmashell", status=True)
    if not pid:
        # threading.Thread(target=self.exec, args=(f"sudo -u pi plasmashell", False,)).start()
        exec("sudo -u pi plasmashell &", False)

def logout_window():
    power_cmd = "qdbus org.kde.LogoutPrompt /LogoutPrompt org.kde.LogoutPrompt.promptShutDown"
    exec(power_cmd)