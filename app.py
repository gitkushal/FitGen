# app.py
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import tempfile, os, json
from io import BytesIO

# local modules
from ai_engine.mri_ai import analyze_report, extract_text_from_file
from ml_recommender import predict_workout
import gamification

# PDF generation
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

app = Flask(__name__)
CORS(app)

@app.route("/")
def home():
    return {"message": "FitGenesis backend running"}

# ----------------------
# Analyze uploaded report
# ----------------------
@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    """
    Expects multipart form:
      - file: uploaded pdf/image/txt
      - user_id: (optional) string to award upload XP in gamification DB
      - age, bmi, experience_level, pain_level (optional) json fields for ML recommender
    """
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    f = request.files['file']
    # save temporary
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(f.filename)[1]) as tmp:
        f.save(tmp.name)
        tmp_path = tmp.name

    try:
        text = extract_text_from_file(tmp_path)
        result = analyze_report(text)

        # optional: call local ML recommender if client sent relevant fields
        ml_input = {}
        if request.form.get("age"):
            try:
                ml_input = {
                    "age": int(request.form.get("age")),
                    "bmi": float(request.form.get("bmi", 24.0)),
                    "condition": request.form.get("condition", "None"),
                    "experience_level": request.form.get("experience_level", "Beginner"),
                    "pain_level": int(request.form.get("pain_level", 0))
                }
                ml_pred = predict_workout(**ml_input)
                result["ml_recommendation"] = {"workout_type": ml_pred}
            except Exception:
                result["ml_recommendation"] = {"error": "ml predict failed"}

        # award upload XP if user_id included
        user_id = request.form.get("user_id")
        if user_id:
            gamification.mark_upload(user_id, note=f"Uploaded {f.filename}")

        return jsonify(result)
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass

# ----------------------
# Generate a printable PDF report from JSON result (POST JSON)
# ----------------------
@app.route("/api/report", methods=["POST"])
def api_report():
    payload = request.get_json()
    if not payload or "result" not in payload:
        return jsonify({"error": "send JSON with key 'result'"}), 400

    result = payload["result"]

    buffer = BytesIO()

    # Build PDF
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=40, leftMargin=40,
                            topMargin=60, bottomMargin=40)
    elements = []
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="SectionTitle",
                              fontSize=14,
                              leading=16,
                              textColor=colors.white,
                              backColor=colors.HexColor("#004aad"),
                              alignment=1))

    styles.add(ParagraphStyle(name="BodyTextCustom",
                              fontSize=11,
                              leading=14))

    wrap_style = ParagraphStyle(name="TableWrap",
                                fontSize=10,
                                leading=13,
                                alignment=0)

    # Title
    elements.append(Paragraph("<b>FitGenesis AI – Personalized Fitness Report</b>", styles['Title']))
    elements.append(Spacer(1, 12))

    # Conditions
    elements.append(Paragraph("Detected Conditions", styles['SectionTitle']))
    for cond in result.get("conditions", []):
        elements.append(Paragraph(f"• {cond}", styles['BodyTextCustom']))
    elements.append(Spacer(1, 10))

    # Exercise plan
    elements.append(Paragraph("Exercise Plan", styles['SectionTitle']))
    if result.get("exercise_plan"):
        data = [["Day", "Exercises"]]
        for day in result["exercise_plan"]:
            data.append([str(day["day"]), ", ".join(day["exercises"])])
        table = Table(data)
        table.setStyle(TableStyle([("GRID", (0,0), (-1,-1), 0.5, colors.grey)]))
        elements.append(table)
    elements.append(Spacer(1, 10))

    # Diet Plan
    elements.append(Paragraph("Diet Plan", styles['SectionTitle']))
    if result.get("diet_plan"):
        data = [["Day", "Meals"]]
        for day in result["diet_plan"]:
            data.append([str(day["day"]), ", ".join(day["meals"])])
        table = Table(data)
        table.setStyle(TableStyle([("GRID", (0,0), (-1,-1), 0.5, colors.grey)]))
        elements.append(table)
    elements.append(Spacer(1, 10))

    # Precautions
    elements.append(Paragraph("Precautions", styles['SectionTitle']))
    for p in result.get("precautions", []):
        elements.append(Paragraph(f"• {p}", styles['BodyTextCustom']))
    elements.append(Spacer(1, 10))

    # Summary
    elements.append(Paragraph("Summary", styles['SectionTitle']))
    elements.append(Paragraph(result.get("summary", ""), styles['BodyTextCustom']))

    doc.build(elements)

    pdf_bytes = buffer.getvalue()
    buffer.close()

    # Return raw PDF bytes directly
    return pdf_bytes, 200, {
        "Content-Type": "application/pdf",
        "Content-Disposition": "attachment; filename=FitGenesis_Report.pdf"
    }

# ----------------------
# Gamification endpoints (wrap gamification.py)
# ----------------------
@app.route("/api/user/create", methods=["POST"])
def route_create_user():
    data = request.get_json()
    user_id = data.get("user_id")
    name = data.get("name", "")
    if not user_id:
        return jsonify({"error": "user_id required"}), 400
    user = gamification.get_or_create_user(user_id, name)
    return jsonify(user)

@app.route("/api/user/<user_id>", methods=["GET"])
def route_get_user(user_id):
    user = gamification.get_user(user_id)
    if not user:
        return jsonify({"error": "not found"}), 404
    return jsonify(user)

@app.route("/api/user/<user_id>/complete", methods=["POST"])
def route_mark_complete(user_id):
    data = request.get_json() or {}
    note = data.get("note", "")
    ok, msg = gamification.mark_daily_completion(user_id, note=note)
    return jsonify({"ok": ok, "message": msg})

@app.route("/api/user/<user_id>/upload", methods=["POST"])
def route_mark_upload(user_id):
    data = request.get_json() or {}
    note = data.get("note", "Uploaded report")
    ok, msg = gamification.mark_upload(user_id, note=note)
    return jsonify({"ok": ok, "message": msg})

@app.route("/api/leaderboard", methods=["GET"])
def route_leaderboard():
    top = int(request.args.get("top", 10))
    lb = gamification.get_leaderboard(top)
    return jsonify(lb)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
