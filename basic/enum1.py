from enum import Enum
import json

Month = Enum('Month', ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'))


class Gender(Enum):
    Male = 0
    Female = 1

class Student:
    def __init__(self, name, gender):
        self.name = name
        self.gender = gender

    def __str__(self):
        return f'Student {self.name} {self.gender}'

    def to_dict(self):
        return {
            "name": self.name,
            "gender": self.gender.name  # 推荐用 .name，语义清晰
        }


def main() -> None:
    for name, member in Month.__members__.items():
        print(name, "=>", member, ",", member.value)

    stu = Student("常益康", Gender.Female)
    stu_json = json.dumps(stu, default=lambda o: o.to_dict(), ensure_ascii=False)
    print(stu_json)
    new_stu = json.loads(stu_json)
    print(new_stu, "new")


if __name__ == "__main__":
    main()
