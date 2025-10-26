import requests
import json

PINATA_API_KEY = "PINATA_API_KEY"
PINATA_SECRET_API_KEY = "PINATA_SECRET_API_KEY"
def pin_to_ipfs(data):
	assert isinstance(data,dict), f"Error pin_to_ipfs expects a dictionary"
	#YOUR CODE HERE
 url = "https://api.pinata.cloud/pinning/pinJSONToIPFS"
    headers = {
        "Content-Type": "application/json",
        "pinata_api_key": PINATA_API_KEY,
        "pinata_secret_api_key": PINATA_SECRET_API_KEY
    }

    response = requests.post(url, headers=headers, data=json.dumps(data))

    if response.status_code != 200:
        raise Exception(f"Error uploading to IPFS: {response.text}")

    cid = response.json()["IpfsHash"]
	return cid

def get_from_ipfs(cid,content_type="json"):
	assert isinstance(cid,str), f"get_from_ipfs accepts a cid in the form of a string"
	#YOUR CODE HERE	
url = f"https://gateway.pinata.cloud/ipfs/{cid}"
    response = requests.get(url)

    if response.status_code != 200:
        raise Exception(f"Error fetching from IPFS: {response.text}")

    if content_type == "json":
        data = response.json()
    else:
        raise ValueError("Unsupported content_type. Only 'json' is supported.")

	assert isinstance(data,dict), f"get_from_ipfs should return a dict"
	return data
