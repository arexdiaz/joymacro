from functools import partial
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