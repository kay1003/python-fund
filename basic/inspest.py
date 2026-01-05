import inspect
from datetime import datetime

print(inspect.signature(datetime.now))  # 查看 now() 需要啥参数
print(inspect.signature(print))         # 查看 print 的参数
print(inspect.signature(len))