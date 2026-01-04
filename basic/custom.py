class Chain(object):
    def __init__(self, path=''):
        self._path = path

    def __getattr__(self, path):
        return Chain(f'{self._path}/{path}')

    def __str__(self):
        return self._path

    __repr__ = __str__


var = Chain().status.user.timeline.list
print(var)

print(callable('kang'))