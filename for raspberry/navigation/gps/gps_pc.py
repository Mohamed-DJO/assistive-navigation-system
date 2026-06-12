import requests


class PCGPS:
    def __init__(self):
        self.api_url = "http://ip-api.com/json/"

    def get_location(self):
        try:
            response = requests.get(self.api_url, timeout=5)
            data = response.json()
            if data["status"] == "success":
                return data["lat"], data["lon"]
            else:
                raise Exception("Location API failed")
        except Exception as e:
            print(f"[GPS] Error: {e}")
            return None, None