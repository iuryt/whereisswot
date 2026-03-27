from flask import Flask, redirect

app = Flask(__name__)

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def catch_all(path):
    return redirect("https://huggingface.co/spaces/iuryt/whereisswot", code=301)
