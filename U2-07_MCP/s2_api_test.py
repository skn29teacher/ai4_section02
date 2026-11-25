# https://jsonplaceholder.typicode.com/
import requests
def test_rest_api():
    base_url = "https://jsonplaceholder.typicode.com"
    endpoint = f'{base_url}/posts'
    payload = {
        'title':"window VScode api Test",
        'body':'Postman과 python 3.13을 활용한 외부 api 호출',
        'userid':1
    }
    header = {"Content-Type":"application/json; charset=UTF-8"}
    # api 요청
    response = requests.post(endpoint,json=payload,headers=header,timeout=10)
    print(f"http status : {response.status_code}")
    data = response.json()
    print('응답본문',data)
    print(f'생성된 id:{data.get("id")}')
if __name__ == "__main__":
    test_rest_api()