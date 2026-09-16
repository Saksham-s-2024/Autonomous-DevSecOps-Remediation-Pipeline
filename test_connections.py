import os
import requests
from dotenv import load_dotenv
from litellm import completion

load_dotenv()

gemini_key = os.getenv("GEMINI_API_KEY")
groq_key = os.getenv("GROQ_API_KEY")

print("Checking available models on your Google key directly...")
url = f"https://generativelanguage.googleapis.com/v1beta/models?key={gemini_key}"
res = requests.get(url).json()

if "models" in res:
    valid_gemini = [
        m["name"].replace("models/", "")
        for m in res["models"]
        if "generateContent" in m.get("supportedGenerationMethods", [])
    ]
    print("Found active Gemini models:", valid_gemini[:3])
    
    target_model = f"gemini/{valid_gemini[0]}"
    print(f"Testing primary candidate: {target_model} ...")
    response = completion(
        model=target_model,
        messages=[{"role": "user", "content": "Respond with the word: ONLINE"}],
        api_key=gemini_key
    )
    print("\nSUCCESS (Google Gemini)! Model Output:", response.choices[0].message.content.strip())

else:
    print("Google API returned error:", res)
    print("\nFalling back to test Groq backup key...")
    response = completion(
        model="groq/llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": "Respond with the word: ONLINE"}],
        api_key=groq_key
    )
    print("\nSUCCESS (Groq Backup)! Model Output:", response.choices[0].message.content.strip())