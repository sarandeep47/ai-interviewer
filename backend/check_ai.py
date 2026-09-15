import os
import json
import logging
from dotenv import load_dotenv

# Load env variables from backend/.env
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(env_path)

gemini_key = os.getenv("GEMINI_API_KEY")
groq_key = os.getenv("GROQ_API_KEY")

print("==================================================")
print("             AI API HEALTH CHECK                  ")
print("==================================================")
print(f"GEMINI_API_KEY present: {bool(gemini_key)} (Length: {len(gemini_key) if gemini_key else 0})")
print(f"GROQ_API_KEY present:   {bool(groq_key)} (Length: {len(groq_key) if groq_key else 0})")
print("--------------------------------------------------")

# 1. Test Groq API
print("\n[1/2] Testing Groq API...")
groq_status = "UNKNOWN"
groq_detail = ""
if not groq_key:
    groq_status = "NOT CONFIGURED"
    groq_detail = "GROQ_API_KEY is missing from environment"
else:
    try:
        from groq import Groq
        cleaned_groq = groq_key.strip().strip('"').strip("'")
        client = Groq(api_key=cleaned_groq)
        model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
        print(f"  Attempting request with model: '{model}'...")
        res = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Respond with OK if you can hear me."}],
            max_tokens=20
        )
        groq_status = "WORKING"
        groq_detail = f"Response: {res.choices[0].message.content.strip()}"
    except Exception as e:
        groq_status = "FAILED"
        groq_detail = f"Error ({type(e).__name__}): {str(e)}"

print(f"--> Groq Status: {groq_status}")
print(f"    Detail: {groq_detail}")

# 2. Test Gemini API
print("\n[2/2] Testing Gemini API...")
gemini_status = "UNKNOWN"
gemini_detail = ""
if not gemini_key:
    gemini_status = "NOT CONFIGURED"
    gemini_detail = "GEMINI_API_KEY is missing from environment"
else:
    try:
        import google.generativeai as genai
        cleaned_gemini = gemini_key.strip().strip('"').strip("'")
        genai.configure(api_key=cleaned_gemini)
        model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        print(f"  Attempting request with model: '{model_name}'...")
        model = genai.GenerativeModel(model_name)
        res = model.generate_content("Respond with OK if you can hear me.")
        gemini_status = "WORKING"
        gemini_detail = f"Response: {res.text.strip()}"
    except Exception as e:
        gemini_status = "FAILED"
        gemini_detail = f"Error ({type(e).__name__}): {str(e)}"

print(f"--> Gemini Status: {gemini_status}")
print(f"    Detail: {gemini_detail}")

print("\n==================================================")
print("                  SUMMARY                         ")
print("==================================================")
print(f"Groq API:   [{groq_status}] - {groq_detail}")
print(f"Gemini API: [{gemini_status}] - {gemini_detail}")
print("==================================================")
