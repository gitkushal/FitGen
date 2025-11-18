# ai_engine/mri_ai.py
import google.generativeai as genai
import re, json, os
from PIL import Image
import pdfplumber
import pytesseract

# ---- configure: replace with your key ----
genai.configure(api_key="GEMINI_API_KEY")
model = genai.GenerativeModel("models/gemini-2.5-flash")

PROMPT_TEMPLATE = """
You are a certified medical fitness assistant.
Analyze the following medical report and generate a 7-day safe exercise and diet plan 
along with precautions and a short summary.

Medical Report:
----------------
{report_text}

Rules:
1. Identify medical condition(s).
2. Suggest low-impact exercises if orthopedic/MRI-related.
3. Suggest balanced diets if metabolic (e.g., diabetes, obesity).
4. Return response ONLY in JSON format:

{{
 "conditions": [],
 "exercise_plan": [{{"day":1, "exercises":[""]}}],
 "diet_plan": [{{"day":1, "meals":[""]}}],
 "precautions": [],
 "summary": ""
}}
"""

def extract_text_from_pdf(path):
    text = ""
    try:
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ""
    except Exception:
        return ""
    return text

def extract_text_from_image(path):
    try:
        return pytesseract.image_to_string(Image.open(path))
    except Exception:
        return ""

def extract_text_from_file(path):
    p = path.lower()
    if p.endswith(".pdf"):
        return extract_text_from_pdf(path)
    if p.endswith((".jpg", ".jpeg", ".png")):
        return extract_text_from_image(path)
    # fallback: read as text
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""

def analyze_report(report_text: str):
    """
    Uses Gemini to analyze. Includes robust JSON extraction and fallback.
    """
    prompt = PROMPT_TEMPLATE.format(report_text=report_text)
    try:
        response = model.generate_content(prompt)
        ai_text = response.text.strip()
        ai_text = ai_text.replace("\\n", " ").replace("\r", " ")
        ai_text = re.sub(r"\s+", " ", ai_text).strip()

        match = re.search(r'\{[\s\S]*\}', ai_text)
        json_str = match.group(0) if match else ai_text

        try:
            ai_json = json.loads(json_str)
        except Exception:
            ai_json = {"raw_output": ai_text}

        # ensure minimal structure
        if "conditions" not in ai_json:
            ai_json = {
                "conditions": ["Unknown"],
                "exercise_plan": [],
                "diet_plan": [],
                "precautions": [],
                "summary": ai_json.get("raw_output", "No structured data.")
            }
        return ai_json
    except Exception as e:
        return {"error": str(e)}
