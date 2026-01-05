from urllib import request
import requests

# with request.urlopen('https://www.baidu.com') as f:
#     data = f.read()
#     print('Status:', f.status, f.reason)
#     for k, v in f.getheaders():
#         print('%s: %s' % (k, v))
#     print('Data:', data.decode('utf-8'))


r = requests.get('https://api.weatherapi.com/v1/current.json?key=b4e8f86b44654e6b86885330242207&q=Beijing&aqi=no') # 豆瓣首页
print(r.status_code)
# for header in r.headers:
#     print(header)
# print(r.json())


r = requests.get('https://www.douban.com/', headers={'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 11_0 like Mac OS X) AppleWebKit'})
print(type(r.headers), r.headers)
for h in r.headers:
    print(h, r.headers[h])
print(r.text)

