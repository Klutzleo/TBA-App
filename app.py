from flask import Flask, render_template, request
import requests

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def index():
    reaction = None
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

    return render_template("index.html", reaction=reaction)

if __name__ == "__main__":
    app.run(debug=True)