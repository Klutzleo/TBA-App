from flask import Flask, render_template, request
import requests
from datetime import datetime
from routes.chat import chat_blp  # ← NEW

app = Flask(__name__)
app.register_blueprint(chat_blp)  # ← NEW

@app.route("/", methods=["GET", "POST"])
def index():
    reaction = None
    reflect_data = None
    current_time = datetime.utcnow().isoformat() + "Z"

    if request.method == "POST":
        payload = {
            "timestamp": request.form["timestamp"],
            "emotion": request.form["emotion"],
            "summary": request.form["summary"]
        }
        response = requests.post(
            "https://tba-app-production.up.railway.app/validate/memory_echoes",
            json=payload
        )
        reaction = response.json().get("reaction")

    reflect_response = requests.get("https://tba-app-production.up.railway.app/reflect")
    if reflect_response.ok:
        reflect_data = reflect_response.json()

    return render_template("index.html", reaction=reaction, current_time=current_time, reflect=reflect_data)

if __name__ == "__main__":
    app.run(debug=True)

application = app