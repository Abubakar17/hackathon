"""
Flask Web Application: Interactive Underwriting Decision Console.
Demonstrates end-to-end processing of messy credit applications into OMG DMN 1.3 models and Decision Objects.
Supports AI Agent (Claude Haiku via Vercel AI Gateway) with offline deterministic fallback.
"""
from flask import Flask, render_template, request, jsonify, send_file
import os

from pipeline import process_credit_application
from samples import SAMPLE_APPLICATIONS
from check_set import CHECK_SET_CASES
from ai_analyst import load_gateway_key

app = Flask(__name__)

@app.route("/")
def index():
    has_key = bool(load_gateway_key())
    return render_template("index.html", has_gateway_key=has_key)

@app.route("/api/sample/<sample_key>")
def get_sample(sample_key):
    sample = SAMPLE_APPLICATIONS.get(sample_key)
    if not sample:
        return jsonify({"error": "Sample not found"}), 404
    return jsonify(sample)

@app.route("/api/decide", methods=["POST"])
def decide():
    data = request.get_json() or {}
    raw_text = data.get("raw_text", "")
    use_ai = bool(data.get("use_ai", True))
    if not raw_text.strip():
        return jsonify({"error": "No application text provided"}), 400

    decision, dmn_xml = process_credit_application(raw_text, output_dir="delivery", use_ai=use_ai)
    return jsonify({
        "decision": decision.to_dict(),
        "dmn_xml": dmn_xml
    })

@app.route("/api/check_set")
def api_check_set():
    results = []
    passed = 0
    total = len(CHECK_SET_CASES)

    for case in CHECK_SET_CASES:
        # Check set runs deterministically for speed and test reproducibility
        dec, _ = process_credit_application(case["text"], use_ai=False)
        ok = (dec.status == case["expected_status"] and dec.ruling_category == case["expected_category"])
        if ok:
            passed += 1
        results.append({
            "id": case["id"],
            "name": case["name"],
            "expected_status": case["expected_status"],
            "expected_category": case["expected_category"],
            "got_status": dec.status,
            "got_category": dec.ruling_category,
            "pass": ok
        })

    return jsonify({
        "passed": passed,
        "total": total,
        "results": results
    })

@app.route("/api/download_dmn")
def download_dmn():
    dmn_path = os.path.join("delivery", "ruling.dmn")
    if os.path.exists(dmn_path):
        return send_file(dmn_path, as_attachment=True, download_name="ruling.dmn", mimetype="application/xml")
    return jsonify({"error": "No DMN generated yet"}), 404

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Credit DMN Ruling Engine running at http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
