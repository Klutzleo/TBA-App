from flask import Flask, jsonify
from routes.schemas import schemas_bp
import os
from dotenv import load_dotenv
from db import Base, engine
from models import Echo


load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


app = Flask(__name__)
app.register_blueprint(schemas_bp)

@app.route("/")
def home():
    return jsonify({"message": "TBA backend is alive!"})

if __name__ == "__main__":
    app.run(debug=True)
    
    
Base.metadata.create_all(bind=engine)
