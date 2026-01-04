from multiprocessing import Process
import os
import time

# 子进程要执行的代码
def run_proc(name):
    time.sleep(2)
    print('Run child process %s (%s)...' % (name, os.getpid()))
    time.sleep(3)

if __name__=='__main__':
    print('Parent process %s.' % os.getpid())
    p = Process(target=run_proc, args=('test',))
    print('Child process will start.')
    p.start()
    p.join()
    print('Child process end.')
