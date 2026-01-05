import argparse

class ReadOnlyName:
    """描述符：让名字只能读，不能改、不能删"""
    def __get__(self, instance, owner):
        # 读取名字时触发
        if instance is None:
            return self
        return instance.__dict__['_name']  # 从私有属性取值

    def __set__(self, instance, value):
        # 设置名字时触发
        if hasattr(instance, '_name'):  # 如果已经设置过了
            raise AttributeError("名字不能修改！")
        instance.__dict__['_name'] = value  # 第一次设置，存起来

    def __delete__(self, instance):
        # 删除名字时触发
        raise AttributeError("名字不能删除！")


class Student:
    nameb = ReadOnlyName()  # 用描述符作为类属性

    def __init__(self, namea):
        self.nameb = namea  # 这里会触发 __set__，设置名字

    @property
    def name(self):
        return self._name

stu = Student('kang')
print(stu.nameb, type(stu))
dict()



# 构造命令行参数:
parser = argparse.ArgumentParser()
parser.add_argument('-u', '--user')
parser.add_argument('-c', '--color')
namespace = parser.parse_args()
command_line_args = { k: v for k, v in vars(namespace).items() if v }
print(command_line_args)