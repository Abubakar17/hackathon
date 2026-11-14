"""
Flask console for the credit decision pipeline.
Run: python app.py  ->  http://localhost:5000
"""
import os

from flask import Flask, Response, jsonify, render_template, request, send_from_directory
from werkzeug.utils import secure_filename

from ai_analyst import MODEL, load_gateway_key
from check_set import run_cases, run_properties
from pdf_reader import MAX_BYTES, MAX_FILES, UploadError, combine, read_upload
from pipeline import latest_review, process_credit_application, replay, review
from policy import STORE
from samples import SAMPLE_APPLICATIONS

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_FILES * MAX_BYTES + 1024 * 1024
SAMPLE_PDF_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "samples_pdf")


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
    return jsonify({"record": record, "policy": STORE.public(), "review": latest_review(record["record_id"])})


@app.route("/api/upload", methods=["POST"])
def upload_route():
    """Uploaded PDF / TXT / MD files -> one text document. Nothing is stored on disk."""
    files = [f for f in request.files.getlist("files") if f and f.filename]
    if not files:
        return jsonify({"error": "No file was uploaded"}), 400
    if len(files) > MAX_FILES:
        return jsonify({"error": f"Upload at most {MAX_FILES} files at a time"}), 400
    read = []
    for f in files:
        name = os.path.basename(f.filename.replace("\\", "/"))[:120]
        try:
            read.append(read_upload(name, f.read(MAX_BYTES + 1)))
        except UploadError as e:
            return jsonify({"error": f"{name}: {e}"}), 400
    return jsonify({"text": combine(read),
                    "files": [{"name": r["name"], "kind": r["kind"], "pages": len(r["pages"]),
                               "chars": sum(len(p) for p in r["pages"])} for r in read]})


@app.errorhandler(413)
def too_large(_e):
    return jsonify({"error": "The upload is too large (4 MB per file)"}), 413


@app.route("/samples/<name>")
def sample_pdf(name):
    return send_from_directory(SAMPLE_PDF_DIR, secure_filename(name), as_attachment=True)


@app.route("/api/review", methods=["POST"])
def review_route():
    data = request.get_json(silent=True) or {}
    try:
        return jsonify({"review": review(str(data.get("record_id")), data.get("action", ""),
                                         data.get("reviewer", ""), data.get("note", ""))})
    except KeyError:
        return jsonify({"error": "This record is not stored, so it cannot be reviewed"}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


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
