class Person:
    def __init__(self, name, age):
        self.name = name
        self.age = age

person = Person("홍길동", 25)
print(vars(person))

# print(vars(person))