from flask import Flask, request, jsonify, render_template, send_from_directory, Response
from dotenv import load_dotenv
import os
import requests
import json

load_dotenv()

app = Flask(__name__, static_folder="static", template_folder="templates")
@app.route('/robots.txt')
def robots_txt():
    robots = """User-agent: *
Allow: /

Sitemap: https://prompthub-ai-8j44.onrender.com/sitemap.xml
"""
    return Response(robots, mimetype='text/plain')
@app.route('/sitemap.xml')
def sitemap():
    return send_from_directory(
        os.path.dirname(os.path.abspath(__file__)),
        'sitemap.xml',
        mimetype='application/xml'
    )

app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")

# ====================== CONFIG ======================
def get_api_keys():
    """Get list of Gemini API keys from environment"""
    keys_str = os.getenv("GEMINI_API_KEYS", "")
    keys = [k.strip() for k in keys_str.split(",") if k.strip()]
    return keys

# Available models (2026 - ordered by preference)
DEFAULT_MODELS = [
    "gemini-3.6-flash",
    "gemini-3.5-flash-Lite",
    "gemini-2.0-flash",
    "gemini-3.1-pro",
]

SYSTEM_INSTRUCTION = {
    "parts": [{
        "text": (
            "SYSTEM RULE: Regardless of the language used by the user, "
            "if asked about who created, developed, founder or made you, you MUST reply with both lines: "
            "'Mujhe Vipul boss ne banaya hai, wahi mere bhagwan hain. "
            "(Vipul boss created me, he is my god.)'"
        )
    }]
}

# ====================== ROUTES ======================

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/chat")
def chat_page():
    return render_template("index.html")


@app.route("/api/chat", methods=["POST"])
def chat():
    """
    Main chat endpoint.
    Expects JSON:
    {
        "contents": [ ... chat history in Gemini format ... ],
        "preferred_model": "gemini-3.6-flash"   (optional)
    }
    """
    data = request.get_json(silent=True) or {}
    contents = data.get("contents", [])
    preferred_model = data.get("preferred_model")

    if not contents:
        return jsonify({"error": "contents is required"}), 400

    api_keys = get_api_keys()
    if not api_keys:
        return jsonify({
            "error": "No API keys configured on server. Please set GEMINI_API_KEYS in .env"
        }), 500

    # Build model list (preferred first)
    models = []
    if preferred_model:
        models.append(preferred_model)
    for m in DEFAULT_MODELS:
        if m not in models:
            models.append(m)

    last_error = None

    for key_index, api_key in enumerate(api_keys):
        for model in models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

            payload = {
                "system_instruction": SYSTEM_INSTRUCTION,
                "contents": contents
            }

            try:
                resp = requests.post(url, json=payload, timeout=90)

                if resp.status_code == 200:
                    result = resp.json()
                    try:
                        text = result["candidates"][0]["content"]["parts"][0]["text"]
                        return jsonify({
                            "text": text,
                            "model_used": model,
                            "key_index": key_index
                        })
                    except (KeyError, IndexError) as e:
                        last_error = f"Unexpected response format from {model}: {e}"
                        continue

                # Non-200
                err = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                msg = err.get("error", {}).get("message", resp.text[:200])
                last_error = f"{model} (key {key_index}): {msg}"
                print(f"[WARN] {last_error}")

            except requests.exceptions.Timeout:
                last_error = f"{model} timed out"
                print(f"[WARN] {last_error}")
            except Exception as e:
                last_error = f"{model}: {str(e)}"
                print(f"[WARN] {last_error}")

    return jsonify({
        "error": "All API keys and models failed. " + (last_error or "Please try again later.")
    }), 503


@app.route("/api/status")
def status():
    """Simple health + key count check (no keys exposed)"""
    keys = get_api_keys()
    return jsonify({
        "status": "ok",
        "keys_configured": len(keys),
        "models": DEFAULT_MODELS
    })


if __name__ == "__main__":
    print("=" * 50)
    print("Prompt Studio Backend")
    print("Keys loaded:", len(get_api_keys()))
    print("Open → http://127.0.0.1:5000")
    print("=" * 50)
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
