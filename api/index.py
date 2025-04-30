import time
import random
import os
import json
from flask import Flask, request, jsonify
from google import genai
from google.genai import types
from collections import deque
from threading import Lock

app = Flask(__name__)

# Configuration
API_KEYS = os.getenv("API_KEYS").split(",")  # Comma-separated list of API 
JSON_FILE = "api_key_state.json"

RESET_INTERVAL = 60  # seconds
MAX_RETRIES = 3  # 2 for Pro, 2 for Flash

# Safety settings
# HARM_CATEGORY_UNSPECIFIED = 'HARM_CATEGORY_UNSPECIFIED' HARM_CATEGORY_HATE_SPEECH = 'HARM_CATEGORY_HATE_SPEECH' HARM_CATEGORY_DANGEROUS_CONTENT = 'HARM_CATEGORY_DANGEROUS_CONTENT' HARM_CATEGORY_HARASSMENT = 'HARM_CATEGORY_HARASSMENT' HARM_CATEGORY_SEXUALLY_EXPLICIT = 'HARM_CATEGORY_SEXUALLY_EXPLICIT' HARM_CATEGORY_CIVIC_INTEGRITY = 'HARM_CATEGORY_CIVIC_INTEGRITY'
#  element predicate failed: $.category in (HarmCategory.HARM_CATEGORY_HATE_SPEECH, HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, HarmCategory.HARM_CATEGORY_HARASSMENT, HarmCategory.HARM_CATEGORY_CIVIC_INTEGRITY)\n', 'status': 'INVALID_ARGUMENT'}}
SAFETY_SETTINGS = [
    types.SafetySetting(
        category="HARM_CATEGORY_HATE_SPEECH",
        threshold="OFF"
    ),
    types.SafetySetting(
        category="HARM_CATEGORY_DANGEROUS_CONTENT",
        threshold="OFF"
    ),
    types.SafetySetting(
        category="HARM_CATEGORY_HARASSMENT",
        threshold="OFF"
    ),
    types.SafetySetting(
        category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
        threshold="OFF"
    ),
    types.SafetySetting(
        category="HARM_CATEGORY_CIVIC_INTEGRITY",
        threshold="OFF"
    ),
]

class APIKeyManager:
    def __init__(self, keys):
        self.keys = deque(keys)
        self.usage = self.load_state()
        if not self.usage:
            self.usage = {key: {
                "pro_count": 0, 
                "pro_daily": 0,
                "flash_count": 0, 
                "flash_daily": 0,
                "last_reset": time.time()
            } for key in keys}
        self.lock = Lock()

    def load_state(self):
        if os.path.exists(JSON_FILE):
            with open(JSON_FILE, 'r') as f:
                return json.load(f)
        return {}

    def save_state(self):
        with open(JSON_FILE, 'w') as f:
            json.dump(self.usage, f)

    def get_available_key(self, model):
        while True:
            with self.lock:
                current_time = time.time()
                for _ in range(len(self.keys)):
                    time.sleep(random.randint(0, 7))
                    self.keys.rotate(-1)
                    key = self.keys[0]
                    if current_time - self.usage[key]["last_reset"] >= RESET_INTERVAL:
                        self.usage[key]["pro_count"] = 0
                        self.usage[key]["flash_count"] = 0
                        self.usage[key]["last_reset"] = current_time
                    
                    if model == "pro" and self.usage[key]["pro_count"] < 2 and self.usage[key]["pro_daily"] < 10000:
                        self.usage[key]["pro_count"] += 1
                        self.usage[key]["pro_daily"] += 1
                        #self.save_state()
                        return key
                    elif model == "flash" and self.usage[key]["flash_count"] < 15 and self.usage[key]["flash_daily"] < 1500:
                        self.usage[key]["flash_count"] += 1
                        self.usage[key]["flash_daily"] += 1
                        #self.save_state()
                        return key
            time.sleep(1)

key_manager = APIKeyManager(API_KEYS)

def get_gemini_response(prompt):
    models = ['gemini-2.0-flash', 'gemini-2.0-flash', 'gemini-2.0-flash', 'gemini-2.0-flash', 'gemini-2.0-flash']
    temperatures = [1.0, 1.0, 1.0, 1.0, 0.5]

    for attempt in range(MAX_RETRIES):
        try:
            model_type = "pro" if attempt < 2 else "flash"
            api_key = key_manager.get_available_key(model_type)
            print(f"Using key: {api_key}, Attempt: {attempt + 1}, Model: {models[attempt]}, Temperature: {temperatures[attempt]}")
            
            # Create client with API key
            client = genai.Client(api_key=api_key)
            
            # Create generation config
            generation_config = types.GenerateContentConfig(
                temperature=temperatures[attempt],
                safety_settings=SAFETY_SETTINGS
            )
            
            # Generate content
            response = client.models.generate_content(
                model=models[attempt],
                contents=prompt,
                config=generation_config
            )
       
            
            print(f"Request successful on attempt {attempt + 1}")
            return response.text
        except Exception as e:
            print(f"Request failed on attempt {attempt + 1}: {str(e)}")
            if attempt == MAX_RETRIES - 1:  # If this was the last attempt
                return f"Error after {MAX_RETRIES} attempts: {str(e)}"
            time.sleep(1)  # Wait a bit before retrying
    
    return "Unexpected error occurred"

@app.route('/')
def hello_world():
    return 'zhy'

@app.route('/key_info')
def key_info():
    return jsonify({key[0:10]: value for key, value in key_manager.usage.items()})

@app.route('/generate', methods=['POST'])
def generate():
    try:
        prompt = request.json.get('prompt')
        if not prompt:
            return jsonify({"error": "No prompt provided"}), 400

        response = get_gemini_response(prompt)
        return jsonify({"response": response})
    
    except Exception as e:
        print("Request failed:", str(e))
        return jsonify({"error": "Internal server error"}), 500

def get_gemini_response2(prompt):
    models = ["gemini-2.0-flash", "gemini-2.0-flash", "gemini-2.5-flash-preview-04-17"]
    temperatures = [1.0, 1.0, 0.5]

    for attempt in range(MAX_RETRIES):
        try:
            model_type = "pro" if attempt < 2 else "flash"
            api_key = key_manager.get_available_key(model_type)
            print(f"Using key: {api_key}, Attempt: {attempt + 1}, Model: {models[attempt]}, Temperature: {temperatures[attempt]}")
            
            # Create client with API key
            client = genai.Client(api_key=api_key)
            
            # Create generation config
            generation_config = types.GenerateContentConfig(
                temperature=temperatures[attempt],
                safety_settings=SAFETY_SETTINGS,
                thinking_config={'thinking_budget': 0}
            )
            
            # Generate content
            response = client.models.generate_content(
                model=models[attempt],
                contents=prompt,
                config=generation_config
            )
            return response.text
        except Exception as e:
            print("error : " + e )
            if attempt == MAX_RETRIES - 1:  # If this was the last attempt
                return f"Error after {MAX_RETRIES} attempts: {str(e)}"
            time.sleep(1)  # Wait a bit before retrying
    
    return "Unexpected error occurred"

@app.route('/generate2', methods=['POST'])
def generate2():
    try:
        prompt = request.json.get('prompt')
        if not prompt:
            return jsonify({"error": "No prompt provided"}), 400

        response = get_gemini_response2(prompt)
        return jsonify({"response": response})
    
    except Exception as e:
        print("Request failed:", str(e))
        return jsonify({"error": "Internal server error"}), 500
    
if __name__ == '__main__':
    app.run(threaded=True, host="0.0.0.0")
