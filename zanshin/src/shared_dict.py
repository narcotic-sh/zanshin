import threading

shared_dict = {
    "processor_status": "loading",
    "active_job_status": None
}

dict_lock = threading.Lock()

def write(key, value):
    with dict_lock:
        shared_dict[key] = value

def read(key):
    with dict_lock:
        return shared_dict.get(key)