def normalize(name):
    first = name[0]
    last = name[1:]
    return first.upper() + last.lower()

# 测试:
L1 = ['adam', 'LISA', 'barT']
L2 = list(map(normalize, L1))
print(L2)