import logging
import netifaces
import requests
import threading
import subprocess

logger = logging.getLogger("main")



'''Commands go here'''
def exec(command):
    result = subprocess.run(command, capture_output=True, shell=True, text=True)
    logger.error(f"{command}: {result.stderr.strip()}") if result.returncode != 0 else None
    return result

def threadedExec(command):
    threading.Thread(target=exec, args=(command,)).start()        


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