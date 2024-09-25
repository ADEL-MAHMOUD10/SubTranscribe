import os
import requests
import time
from flask import Flask, request, jsonify, render_template, redirect, url_for, send_file
from werkzeug.utils import secure_filename
import moviepy.editor as mp
from datetime import datetime
import warnings

warnings.filterwarnings("ignore", category=SyntaxWarning)

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "/tmp"  # Corrected the folder name to "uploads"

progress = {"status": 0, "message": "Initializing"}

@app.route('/about')
def about():
    return render_template('about.html')

def upload_audio_to_assemblyai(audio_path):
    global progress

    headers = {"authorization": "2ba819026c704d648dced28f3f52406f"}
    base_url = "https://api.assemblyai.com/v2"
    
    with open(audio_path, "rb") as f:
        response = requests.post(base_url + "/upload", headers=headers, data=f)

    upload_url = response.json()["upload_url"]
    
    # Passing the webhook URL
    data = {
        "audio_url": upload_url,
        "webhook_url": "https://subtranscribe2.vercel.app"  # Replace with your Vercel URL
    }
    response = requests.post(base_url + "/transcript", json=data, headers=headers)
    transcript_id = response.json()['id']
    
    progress["message"] = "Uploading"
    progress["status"] = 15  # Update the status after starting the upload
    time.sleep(5)  # Wait a bit before starting monitoring

    return transcript_id

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    # Log the entire payload for debugging
    print(f"Received webhook data: {data}")

    # Check if 'id' is in the payload
    if 'id' in data:
        transcript_id = data['id']
        # Here you can update processing status in the database or log events
        print(f"Transcription {transcript_id} completed.")
        return render_template('error.html'), 200
    else:
        return render_template('error.html'), 400  # Return a bad request status if 'id' is not found



def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'.mp4', '.wmv', '.mov', '.mkv', '.h.264', '.mp3', '.wav'}
    return '.' in filename and os.path.splitext(filename)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/progress')
def progress_status():
    return jsonify(progress)

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    global progress
    progress = {"status": 0, "message": "Initializing"}

    if request.method == 'POST':
        file = request.files['file']
        time.sleep(1)
        if not allowed_file(file.filename):
            return render_template("error.html")

        # Ensure the upload folder exists
        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'])

        progress["status"] = 10
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        try:
            # Save the file to the desired location
            file.save(file_path)
            file_extension = os.path.splitext(file_path)[1].lower()

            # Handle video to audio conversion
            if file_extension in [".mp4", ".wmv", ".mov", ".mkv", ".h.264"]:
                video = mp.VideoFileClip(file_path)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                audio_file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"audio_{timestamp}.mp3")
                video.audio.write_audiofile(audio_file_path)
                video.reader.close()
                video.audio.reader.close_proc()
                progress["status"] = 25
                progress["message"] = "Converting To Audio file"
                os.remove(file_path)

            elif file_extension in [".mp3", ".wav"]:
                audio_file_path = file_path
                progress["status"] = 30
                progress["message"] = "Uploading audio file"  
            else:
                os.remove(file_path)
                return render_template("error.html")

            progress["status"] = 40
            transcript_id = upload_audio_to_assemblyai(audio_file_path)
            return redirect(url_for('download_subtitle', transcript_id=transcript_id))
        except Exception as e:
            progress["status"] = 0
            progress["message"] = "Error: " + str(e)
            return render_template("error.html")

    return render_template('index.html')

@app.route('/download/<transcript_id>', methods=['GET', 'POST'])
def download_subtitle(transcript_id):
    progress["message"] = "Processing Complete"
    progress["status"] = 100
    if request.method == 'POST':
        file_format = request.form['format']
        headers = {"authorization": "2ba819026c704d648dced28f3f52406f"}
        url = f"https://api.assemblyai.com/v2/transcript/{transcript_id}/{file_format}"

        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            timesub = datetime.now().strftime("%Y%m%d_%H%M%S")
            subtitle_file = f"subtitle_{timesub}.{file_format}"
            subtitle_path = os.path.join(app.config['UPLOAD_FOLDER'], subtitle_file)
            with open(subtitle_path, 'w') as f:
                f.write(response.text)
            
            return redirect(url_for('serve_file', filename=subtitle_file))
        else:
            return f"Error: {response.status_code} {response.reason}"

    return render_template('subtitle.html')

@app.route('/serve/<filename>')
def serve_file(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    if os.path.exists(file_path):
        try:
            response = send_file(file_path, as_attachment=True)
            
            try:
                os.remove(file_path)
            except PermissionError:
                time.sleep(1) 
            
            return response
        except Exception:
            return render_template("error.html")
        except FileNotFoundError:
            return render_template("error.html")
        except TypeError:
            return render_template("error.html")
    
if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    app.run(debug=True, host="0.0.0.0")
