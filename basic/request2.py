from urllib import request
import json
import os


def fetch_data(url):
    with request.urlopen(url) as response:
        _str = response.read().decode('utf-8')
        return json.loads(_str)


def main() -> None:
    api_key = os.getenv("WEATHER_API_KEY")
    if not api_key:
        raise RuntimeError("Missing WEATHER_API_KEY environment variable.")

    # 测试
    url = f"https://api.weatherapi.com/v1/current.json?key={api_key}&q=Beijing&aqi=no"
    data = fetch_data(url)
    print(type(data), data)
    assert data["location"]["name"] == "Beijing"
    print("ok")


if __name__ == "__main__":
    main()
