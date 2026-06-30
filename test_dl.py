import requests
BASE_URL = "https://pastpapers.papacambridge.com/directories/CAIE/CAIE-pastpapers/upload/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://pastpapers.papacambridge.com/"
}
url = BASE_URL + "0610_s22_qp_21.pdf"
response = requests.get(url, headers=HEADERS, timeout=10)
print(response.status_code)
print(response.headers.get('Content-Type'))
print(response.content[:50])
