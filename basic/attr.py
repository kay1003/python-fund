import argparse


class ReadOnlyName:
    """描述符：让名字只能读，不能改、不能删"""

    def __get__(self, instance, owner):
        if instance is None:
            return self
        return instance.__dict__["_name"]

    def __set__(self, instance, value):
        if hasattr(instance, "_name"):
            raise AttributeError("名字不能修改！")
        instance.__dict__["_name"] = value

    def __delete__(self, instance):
        raise AttributeError("名字不能删除！")


class Student:
    nameb = ReadOnlyName()

    def __init__(self, namea):
        self.nameb = namea

    @property
    def name(self):
        return self._name


def main() -> None:
    stu = Student("kang")
    print(stu.nameb, type(stu))

    parser = argparse.ArgumentParser()
    parser.add_argument("-u", "--user")
    parser.add_argument("-c", "--color")
    namespace = parser.parse_args()
    command_line_args = {k: v for k, v in vars(namespace).items() if v}
    print(command_line_args)


if __name__ == "__main__":
    main()
