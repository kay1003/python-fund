from enum import Enum, unique
import json

Month = Enum('Month', ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'))


for name, member in Month.__members__.items():
    print(name, '=>', member, ',', member.value)




class Gender(Enum):
    Male = 0
    Female = 1

class Student:
    def __init__(self, name, gender):
        self.name = name
        self.gender = gender

    def __str__(self):
        return f'Student {self.name} {self.gender}'

    def __dict__(self):
        return {
            "name": self.name,
            "gender": self.gender.name  # 推荐用 .name，语义清晰
        }


# 测试:
stu = Student('常益康', Gender.Female)
stuJson = json.dumps(stu, default=lambda o: o.__dict__(),ensure_ascii=False)
print(stuJson)
newStu = json.loads(stuJson)
print(newStu, 'new')
