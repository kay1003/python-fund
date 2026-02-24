import os
from urllib import request

import requests

def main() -> None:
    # with request.urlopen('https://www.baidu.com') as f:
    #     data = f.read()
    #     print('Status:', f.status, f.reason)
    #     for k, v in f.getheaders():
    #         print('%s: %s' % (k, v))
    #     print('Data:', data.decode('utf-8'))

    api_key = os.getenv("WEATHER_API_KEY")
    if not api_key:
        raise RuntimeError("Missing WEATHER_API_KEY environment variable.")

    r = requests.get(
        f"https://api.weatherapi.com/v1/current.json?key={api_key}&q=Beijing&aqi=no",
        timeout=10,
    )
    print(r.status_code)
    # for header in r.headers:
    #     print(header)
    # print(r.json())


    r = requests.get(
        "https://www.douban.com/",
        headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 11_0 like Mac OS X) AppleWebKit"},
        timeout=10,
    )
    print(type(r.headers), r.headers)
    for h in r.headers:
        print(h, r.headers[h])
    print(r.text)


if __name__ == "__main__":
    main()
