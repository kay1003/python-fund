def normalize(name: str) -> str:
    first = name[0]
    last = name[1:]
    return first.upper() + last.lower()


def main() -> None:
    # 测试:
    l1 = ["adam", "LISA", "barT"]
    l2 = list(map(normalize, l1))
    print(l2)


if __name__ == "__main__":
    main()
