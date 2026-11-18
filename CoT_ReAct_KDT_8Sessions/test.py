class Sample:    
    def __call__(self,messages):
        print(f'{messages} 님 저를 부르셨나요?')


s = Sample()
s("홍길동")