from urllib import request
import json


def fetch_data(url):
    with request.urlopen(url) as response:
        _str = response.read().decode('utf-8')
        return json.loads(_str)


# 测试
URL = 'https://api.weatherapi.com/v1/current.json?key=b4e8f86b44654e6b86885330242207&q=Beijing&aqi=no'
data = fetch_data(URL)
print(type(data), data)
assert data['location']['name'] == 'Beijing'
print('ok')
