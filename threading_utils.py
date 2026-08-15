import threading
from concurrent.futures import ThreadPoolExecutor

from gi.repository import GLib


def _async(func):
    def wrapper(*args, **kwargs):
        thread = threading.Thread(target=func, args=args, kwargs=kwargs)
        thread.daemon = True
        thread.start()
        return thread
    return wrapper


def _idle(func):
    def wrapper(*args):
        GLib.idle_add(func, *args)
    return wrapper


image_pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix="fc-images")
api_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="fc-api")
