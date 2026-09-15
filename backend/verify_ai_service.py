import os
import sys

# Force UTF-8 stdout on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(env_path)

sys.path.insert(0, os.path.dirname(__file__))

from services.ai_service import AIService

print("==================================================")
print("      AISERVICE END-TO-END AI API CHECK           ")
print("==================================================")

# 1. Test Groq JSON Call
print("\n[1] Testing Groq JSON response generation...")
try:
    from groq import Groq
    groq_key = os.getenv("GROQ_API_KEY").strip().strip('"').strip("'")
    client = Groq(api_key=groq_key)
    model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "Return valid JSON."},
            {"role": "user", "content": "Return a JSON object with key 'status' set to 'ok' and key 'api' set to 'groq'."}
        ],
        response_format={"type": "json_object"}
    )
    res_content = response.choices[0].message.content
    print(f"--> Groq JSON Success! Content: {res_content}")
except Exception as e:
    print(f"--> Groq JSON Failed! Error: {e}")

# 2. Test Gemini JSON Call
print("\n[2] Testing Gemini JSON response generation...")
try:
    import google.generativeai as genai
    gemini_key = os.getenv("GEMINI_API_KEY").strip().strip('"').strip("'")
    genai.configure(api_key=gemini_key)
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    
    model = genai.GenerativeModel(model_name)
    response = model.generate_content(
        "Return a JSON object with key 'status' set to 'ok' and key 'api' set to 'gemini'.",
        generation_config={"response_mime_type": "application/json"}
    )
    print(f"--> Gemini JSON Success! Content: {response.text.strip()}")
except Exception as e:
    print(f"--> Gemini JSON Failed! Error: {e}")

# 3. Test AIService methods
print("\n[3] Testing AIService.evaluate_candidate_answer()...")
try:
    eval_res = AIService.evaluate_candidate_answer(
        question_text="What is FastAPI?",
        candidate_answer="FastAPI is a modern, fast web framework for building APIs with Python.",
        target_role="Backend Developer"
    )
    print(f"--> AIService Evaluation Result: {eval_res}")
except Exception as e:
    print(f"--> AIService Evaluation Failed: {e}")

print("\n==================================================")
