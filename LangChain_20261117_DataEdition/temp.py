def calc(num1,num2,myfunc):
    return myfunc(num1,num2)

print( calc(10,5, (lambda a,b:a*b)   ) )