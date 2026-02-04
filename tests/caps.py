import time
import os
import socket

def add(a, b):
    return a + b

def return_big(n):
    return "x" * n

def sleepy(ms):
    time.sleep(ms / 1000.0)
    return ms

def getcwd():
    return os.getcwd()

def try_socket():
    s = socket.socket()
    s.close()
    return True

def init_counter():
    path = os.environ.get("CAP_CLOSE_PATH")
    if path:
        with open(path, "w", encoding="utf-8") as f:
            f.write("init\n")
    return {"path": path}

def close_counter(state):
    if not state:
        return
    path = state.get("path")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as f:
        f.write("close\n")
