"""
Flask console for the credit decision pipeline.
Run: python app.py  ->  http://localhost:5000
"""
import os

from flask import Flask, Response, jsonify, render_template, request

from ai_analyst import MODEL, load_gateway_key
from check_set import run_cases, run_properties
from pipeline import process_credit_application, replay
from policy import STORE
from samples import SAMPLE_APPLICATIONS

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html", has_gateway_key=bool(load_gateway_key()), model=MODEL)


@app.route("/api/sample/<sample_key>")
def get_sample(sample_key):
    sample = SAMPLE_APPLICATIONS.get(sample_key)
    if not sample:
        return jsonify({"error": "Sample not found"}), 404
    return jsonify(sample)


@app.route("/api/decide", methods=["POST"])
def decide_route():
    data = request.get_json(silent=True) or {}
    raw_text = data.get("raw_text") or ""
    if not raw_text.strip():
        return jsonify({"error": "No application text provided"}), 400
    record = process_credit_application(raw_text, use_ai=bool(data.get("use_ai", True)))
    return jsonify({"record": record, "policy": STORE.public()})


@app.route("/api/policy")
def policy_route():
    return jsonify(STORE.public())


@app.route("/api/policy/edit", methods=["POST"])
def policy_edit():
    data = request.get_json(silent=True) or {}
    try:
        STORE.edit(str(data.get("rule_id")), str(data.get("input")), str(data.get("test", "")))
    except ValueError as e:
        return jsonify({"error": str(e), "policy": STORE.public()}), 400
    return jsonify({"policy": STORE.public()})


@app.route("/api/policy/reset", methods=["POST"])
def policy_reset():
    STORE.reset()
    return jsonify({"policy": STORE.public()})


@app.route("/api/replay", methods=["POST"])
def replay_route():
    data = request.get_json(silent=True) or {}
    try:
        return jsonify(replay(str(data.get("record_id"))))
    except KeyError as e:
        return jsonify({"error": f"Cannot replay: {e}"}), 404


@app.route("/api/check_set")
def api_check_set():
    cases, props = run_cases(), run_properties()
    return jsonify({"cases": cases, "properties": props, "policy_version": STORE.current()["version"],
                    "passed": sum(c["pass"] for c in cases), "total": len(cases)})


@app.route("/api/dmn")
def download_dmn():
    cur = STORE.current()
    return Response(cur["xml"], mimetype="application/xml",
                    headers={"Content-Disposition": f'attachment; filename="credit-policy-v{cur["version"]}-{cur["sha"]}.dmn"'})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Credit decision console: http://localhost:{port}")
    app.run(host="127.0.0.1", port=port, debug=False)
