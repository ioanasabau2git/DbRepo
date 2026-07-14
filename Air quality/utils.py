
from config import OpenAQ_API_KEY
import requests

url = 'https://api.openaq.org/v3/locations?coordinates=38.907%2C-77.037&radius=1000&providers_id=1&limit=100&page=1&order_by=id&sort_order=asc&iso=US&countries_id=1&bbox=-77.1200%2C38.7916%2C-76.9094%2C38.9955'
response = requests.get(url, headers={'X-API-Key': OpenAQ_API_KEY})

print(response)