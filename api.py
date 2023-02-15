from flask import Flask, request, send_from_directory, send_file
import ysf, shutil, time, os

app = Flask(__name__)


@app.route("/")
def hello():
    return send_from_directory('','index.html')


@app.route("/api", methods=['POST'])
def proc():
    t = time.time()
    # print(request.files)
    file = request.files.get("img")
    filename = file.filename
    filetype = file.content_type
    print(filename, filetype)
    file.save(os.path.join("images", file.filename))

    callsign = request.form['callsign']
    radioid = request.form['radioid']

    # print(callsign, radioid)

    ysf.main(callsign, radioid, f"output{t}", "images/" + filename)

    shutil.make_archive(f"output{t}", "zip", f"output{t}")

    return send_file(f"output{t}.zip")
