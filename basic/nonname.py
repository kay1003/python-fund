def is_odd(n):
    return n % 2 == 1

def main() -> None:
    l = list(filter(is_odd, range(1, 20)))
    print(l)

    print(list(filter(lambda x: x % 2 == 1, range(1, 20))))

    def now():
        print("2024-6-1")
        return "kang"

    f = now
    print(f, type(f))
    print(f.__name__, ":", f())

    var = list(range(11))
    print(var)
    var = var[10:0:-2]
    print(var)


if __name__ == "__main__":
    main()

