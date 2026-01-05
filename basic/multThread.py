import threading, multiprocessing
from datetime import *

def loop():
    print(f'loop start name{threading.current_thread().name}')
    x = 0
    while True:
        x = x ^ 1


# for i in range(multiprocessing.cpu_count()):
#     threading.Thread(target=loop, name=f'kang{i}').start()

threadLocal = threading.local

print(datetime.now().astimezone(timezone(timedelta(hours=1))))