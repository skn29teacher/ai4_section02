class MyObj:
    name = '홍길동'

obj = MyObj()
print(obj.name)

print(getattr(obj,'age','나이필드가 없습니다.' ))