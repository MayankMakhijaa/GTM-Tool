from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
import os
import time
from typing import List, Dict, Any
from dotenv import load_dotenv

from parser import parse_pasted_comments
from analyzer import analyze_comments
from excel import generate_excel
from historical import get_historical_email_leads, get_all_historical_leads

load_dotenv()

app = Flask(__name__)
CORS(app)

OUTPUT_DIR = os.path.join(os.getcwd(), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json()
    if not data or not isinstance(data, dict):
        return jsonify({"success": False, "error": "Please provide pasted LinkedIn comments."}), 400
    
    raw_text = str(data.get("comments_text") or data.get("pasted_text") or data.get("text") or "").strip()
    if not raw_text:
        return jsonify({"success": False, "error": "Please paste LinkedIn comments before generating leads."}), 400
    
    start_time = time.time()
    
    # 1. Parse raw pasted text using local Python parser
    parsed_comments = parse_pasted_comments(raw_text)
    if not parsed_comments:
        return jsonify({"success": False, "error": "No valid comments could be extracted from the pasted text. Please check your copy-paste content."}), 400
        
    # 2. Analyze comments deterministically with Gemini
    analyzed_comments = analyze_comments(parsed_comments)
    if not isinstance(analyzed_comments, list) or len(analyzed_comments) == 0:
        return jsonify({"success": False, "error": "Lead analysis could not be completed. Please try again."}), 500
        
    # 3. Filter qualified leads
    qualified_leads: List[Dict[str, Any]] = [c for c in analyzed_comments if isinstance(c, dict) and c.get("lead") is True]
        
    # 4. Generate Excel
    filename = generate_excel(analyzed_comments)
    
    # Calculate average intent score
    scores = [c.get("lead_score", 0) for c in qualified_leads if isinstance(c.get("lead_score"), (int, float))]
    avg_score = sum(scores) / len(scores) if len(scores) > 0 else 0
    
    processing_time = round(time.time() - start_time, 1)
    
    # Sort leads by score descending for the UI
    qualified_leads.sort(key=lambda x: x.get("lead_score", 0), reverse=True)
    
    return jsonify({
        "success": True,
        "comments_analyzed": len(parsed_comments),
        "qualified_leads_count": len(qualified_leads),
        "avg_lead_intent": round(avg_score, 1),
        "processing_time": processing_time,
        "leads": qualified_leads,
        "download_url": f"/download/{filename}"
    })

@app.route("/api/email-leads", methods=["GET"])
def get_email_leads():
    """
    Returns deduplicated email-qualified leads consolidated from all Excel files in output/
    """
    leads = get_historical_email_leads()
    return jsonify({
        "success": True,
        "count": len(leads),
        "leads": leads
    })

@app.route("/api/history-leads", methods=["GET"])
def get_history_leads():
    """
    Returns ALL deduplicated historical qualified leads consolidated from all Excel files in output/
    (regardless of email availability)
    """
    leads = get_all_historical_leads()
    return jsonify({
        "success": True,
        "count": len(leads),
        "leads": leads
    })

@app.route("/download/<path:filename>", methods=["GET"])
def download_file(filename):
    # Prevent arbitrary file access
    safe_path = os.path.normpath(filename)
    if safe_path.startswith("..") or "/" in safe_path or "\\" in safe_path:
        return jsonify({"error": "Invalid filename"}), 400
        
    return send_from_directory(OUTPUT_DIR, safe_path, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
