import requests

def get_weather(location):
    # wttr.in is a weather service that provides weather information in a text format
    url = f"https://wttr.in/{location}?M&format=j1"
    response = requests.get(url)
    data = response.json()
    return data

def get_weather_func_def():
    return {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the weather information for a location.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The location to get the weather information for. (For example: 'Cologne'",
                    },
                },
                "required": ["location"],
                "additionalProperties": False,
            },
        }
    }
