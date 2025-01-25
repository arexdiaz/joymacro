import logging
import os

def setLogConfig(name):
    formatter = logging.Formatter(fmt="%(asctime)s - %(levelname)s - %(module)s - %(message)s")

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    script_path = os.path.dirname(os.path.abspath(__file__))
    file_handler = logging.FileHandler(os.path.join(script_path, "info.log"))
    file_handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)
    logger.addHandler(handler)
    return logger
