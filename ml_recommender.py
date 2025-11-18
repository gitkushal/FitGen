# ml_recommender.py
import joblib, os, numpy as np

MODEL_PATH = "workout_model.pkl"
ENCODERS_PATH = "label_encoders.pkl"

def predict_workout(age=30, bmi=24.0, condition="None", experience_level="Beginner", pain_level=0):
    """
    Loads model+encoders if available. If not, returns a rule-based fallback.
    """
    try:
        if os.path.exists(MODEL_PATH) and os.path.exists(ENCODERS_PATH):
            model = joblib.load(MODEL_PATH)
            encoders = joblib.load(ENCODERS_PATH)
            cond_enc = encoders["condition"].transform([condition])[0]
            exp_enc = encoders["experience_level"].transform([experience_level])[0]
            X = np.array([[age, bmi, cond_enc, exp_enc, int(pain_level)]])
            y = model.predict(X)[0]
            return encoders["workout_type"].inverse_transform([y])[0]
    except Exception:
        pass

    # fallback rule-based
    if pain_level >= 6 or "back" in condition.lower() or "knee" in condition.lower() or "arthritis" in condition.lower():
        return "Rehab Physiotherapy"
    if bmi >= 30 or "obesity" in condition.lower():
        return "Low-Impact Cardio"
    if age < 30 and int(pain_level) <= 2:
        return "Strength Training"
    return "General Wellness"
