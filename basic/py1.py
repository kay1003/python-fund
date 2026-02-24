def main() -> None:
    # 外部输入
    # name = input()
    # print(name)

    num = abs(-45)
    print(num)

    def f(n):
        return n**n

    _ = f(3)

    re_map = map(str, [1, 2, 3, 4, 5, 6, 7])
    print(re_map, type(re_map))
    print(list(re_map))


if __name__ == "__main__":
    main()
