import multiprocessing
import threading
import time
from datetime import datetime, timedelta, timezone

def loop():
    print(f'loop start name{threading.current_thread().name}')
    x = 0
    while True:
        x = x ^ 1
        time.sleep(0.01)


def main() -> None:
    # for i in range(multiprocessing.cpu_count()):
    #     threading.Thread(target=loop, name=f'kang{i}').start()

    thread_local = threading.local()
    _ = thread_local

    print(datetime.now().astimezone(timezone(timedelta(hours=1))))


if __name__ == "__main__":
    main()
