import json
import socket
from random import random
from time import sleep

from antiintuit.config import Config
from antiintuit.logger import get_logger, get_host_and_port

__all__ = [
    "wait_in_the_queue",
    "get_out_of_the_queue"
]

logger = get_logger("antiintuit", "tests_solver", "queue_solution")


def send_message(host, port, message):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((host, port))
        sock.sendall(bytes(message + "\n", "utf-8"))
        received = json.loads(str(sock.recv(1024), "utf-8"))
    logger.debug("Sent: %s\nReceived: %s", message, repr(received))
    return received


def wait_in_the_queue():
    if Config.TEST_SOLVER_SESSION_QUEUE_HOST is None:
        sleep_time = random.random() * Config.MAX_LATENCY_FOR_OUT_OF_SYNC
        logger.debug("Session '%s' is sleeping during %f", Config.SESSION_ID, sleep_time)
        sleep(sleep_time)
        return
    host, port = get_host_and_port(Config.TEST_SOLVER_SESSION_QUEUE_HOST, 26960)
    message = "CHK:" + Config.SESSION_ID
    received = send_message(host, port, message)
    while not isinstance(received, dict) or not received["allow"]:
        logger.debug("The session '%s' is in the queue and has %i position.", Config.SESSION_ID, received["pos"])
        sleep(2)
        received = send_message(host, port, message)


def get_out_of_the_queue():
    if Config.TEST_SOLVER_SESSION_QUEUE_HOST is not None:
        host, port = get_host_and_port(Config.TEST_SOLVER_SESSION_QUEUE_HOST, 26960)
        message = "DEL:" + Config.SESSION_ID
        received = send_message(host, port, message)
        assert received is True, "Received not True from the Session Queue"