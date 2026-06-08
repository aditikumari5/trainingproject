import google.generativeai as genai
from django.conf import settings

genai.configure(api_key=settings.GEMINI_API_KEY)

model = genai.GenerativeModel("gemini-1.5-flash")

def get_ai_response(question):
    try:
        response = model.generate_content(question)
        return response.text

    except Exception:
        return "🤖 I'm unable to answer right now."