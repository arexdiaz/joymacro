import logging
import subprocess
import os
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