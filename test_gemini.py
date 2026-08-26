import os, dotenv; dotenv.load_dotenv("config/.env")
from google import genai
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
response = client.models.generate_content(model="gemini-3.6-flash", contents="Hello Gemini")
print("Response:", response.text)
