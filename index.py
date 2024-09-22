import os
import requests
import time
import sqlite3
import shutil
from flask import Flask, request, jsonify, render_template, redirect, url_for, send_file
from werkzeug.utils import secure_filename
import moviepy.editor as mp
from datetime import datetime


app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "/tmp"

temp_db_path = '/tmp/database.db'

def create_db():
    with sqlite3.connect(temp_db_path) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS progress
                    (id TEXT PRIMARY KEY, status INTEGER, message TEXT, date DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        conn.commit()
    
def update_progress(transcript_id, status, message):
    conn = sqlite3.connect('progress.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO progress (id, status, message) VALUES (?, ?, ?)",
              (transcript_id, status, message))
    conn.commit()
    conn.close()

def get_progress(transcript_id):
    conn = sqlite3.connect('progress.db')
    c = conn.cursor()
    c.execute("SELECT status, message FROM progress WHERE id=?", (transcript_id,))
    row = c.fetchone()
    conn.close()
    return row if row else (0, "Initializing")


progress = {"status": 0, "message": "Initializing"}

def upload_audio_to_assemblyai(audio_path):
    headers = {"authorization": "2ba819026c704d648dced28f3f52406f"}
    base_url = "https://api.assemblyai.com/v2"
    
   
    with open(audio_path, "rb") as f:
        response = requests.post(base_url + "/upload", headers=headers, data=f)
    
    upload_url = response.json()["upload_url"]
    data = {"audio_url": upload_url}
    response = requests.post(base_url + "/transcript", json=data, headers=headers)
    transcript_id = response.json()['id']
    polling_endpoint = f"https://api.assemblyai.com/v2/transcript/{transcript_id}"
    
   
    progress["message"] = "Uploading"
    while progress["status"] < 25:
        progress["status"] += 1
        time.sleep(0.1)
    
    
    progress["status"] = 50
    progress["message"] = "Processing"
    
   
    while progress["status"] < 90:
        progress["status"] += 5
        time.sleep(0.5)
    
    
    while True:
        transcription_result = requests.get(polling_endpoint, headers=headers).json()
        if transcription_result['status'] == 'completed':
            progress["status"] = 100
            update_progress(transcript_id, status=100, message="completed")
            progress["message"] = "Complete"
            os.remove(audio_path) 
            return transcript_id
        elif transcription_result['status'] == 'error':
            raise RuntimeError(f"Transcription failed: {transcription_result['error']}")
        else:
            time.sleep(10)  

@app.route('/progress')
def progress_status():
    return jsonify(progress)

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    global progress
    progress = {"status": 0, "message": "Initializing"}
    if request.method == 'POST':
            file = request.files['file']
            progress["status"] += 1
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            file_extension = os.path.splitext(file_path)[1].lower()

            if file_extension in [".mp4", ".wmv", ".mov", ".mkv", ".h.264"]:
                video = mp.VideoFileClip(file_path)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                audio_file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"audio_{timestamp}.mp3")
                video.audio.write_audiofile(audio_file_path)
                video.reader.close()
                video.audio.reader.close_proc()

                progress["message"] = "Converting To Audio file"
                os.remove(file_path)

            elif file_extension in [".mp3", ".wav"]:
                audio_file_path = file_path
                progress["message"] = "Uploading audio file"  
            else:
                os.remove(file_path)
                update_progress(transcript_id, status=0, message="Error File")

            transcript_id = upload_audio_to_assemblyai(audio_file_path)
            return redirect(url_for('download_subtitle', transcript_id=transcript_id))

        
    return render_template('index.html')
    
@app.route('/download/<transcript_id>', methods=['GET', 'POST'])
def download_subtitle(transcript_id):
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
        response = send_file(file_path, as_attachment=True)
            
        for _ in range(1):  
            try:
                os.remove(file_path)
                break
            except PermissionError:
                time.sleep(1)
            
        return response
if __name__ == '__main__':
    if not os.path.exists('/tmp'):
        os.makedirs('tmp')
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    create_db()
    app.run(debug=True)
