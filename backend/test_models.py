import os
from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(env_path)

groq_key = os.getenv("GROQ_API_KEY")
gemini_key = os.getenv("GEMINI_API_KEY")

print("--- TESTING GROQ MODELS ---")
if groq_key:
    from groq import Groq
    cleaned_groq = groq_key.strip().strip('"').strip("'")
    client = Groq(api_key=cleaned_groq)

    # 1. List available models if supported
    try:
        models = client.models.list()
        model_ids = [m.id for m in models.data]
        print(f"Available Groq Models ({len(model_ids)}): {model_ids[:10]}")
    except Exception as e:
        print(f"Could not list models: {e}")

    # Test default GROQ_MODEL from env vs llama-3.3-70b-versatile
    for test_model in [os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"), "llama-3.3-70b-versatile", "llama-3.1-8b-instant"]:
        try:
            res = client.chat.completions.create(
                model=test_model,
                messages=[{"role": "user", "content": "Respond with 'Hello from Groq!'"}]
            )
            text = res.choices[0].message.content
            print(f"Model '{test_model}': SUCCESS -> '{text}'")
        except Exception as e:
            print(f"Model '{test_model}': FAILED -> {e}")

print("\n--- TESTING GEMINI MODELS ---")
if gemini_key:
    import google.generativeai as genai
    cleaned_gemini = gemini_key.strip().strip('"').strip("'")
    genai.configure(api_key=cleaned_gemini)
    
    for test_model in [os.getenv("GEMINI_MODEL", "gemini-2.5-flash"), "gemini-1.5-flash", "gemini-1.5-pro"]:
        try:
            model = genai.GenerativeModel(test_model)
            res = model.generate_content("Respond with 'Hello from Gemini!'")
            print(f"Model '{test_model}': SUCCESS -> '{res.text.strip()}'")
        except Exception as e:
            print(f"Model '{test_model}': FAILED -> {e}")
