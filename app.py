from flask import Flask, request, send_file, render_template, redirect, url_for
from PIL import ImageFont, ImageDraw, Image
from gtts import gTTS
from moviepy.editor import ImageSequenceClip, AudioFileClip
from pydub import AudioSegment
import numpy as np
import os
import uuid
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Variables for customization
TEXT_SPEED = 24  # frames per second
TEXT_COLOR = (0, 0, 0)
FONT_SIZE = 180
TIMING_ADJUSTMENT = -0.3  # Adjusts the duration of each word in the video
VIDEO_SIZE = (1080, 1920)
BACKGROUND_INTERVALS = [10, 22, 35]  # Change intervals in seconds for background images

# Configure upload folder and allowed extensions
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'txt', 'ttf', 'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def text_to_video(text, font_path, background_images, outputfile):
    words = text.split()
    images = []
    durations = []

    fnt = ImageFont.truetype(font_path, FONT_SIZE)

    # Generate speech for the whole text and save as a temporary file
    tts = gTTS(text=text, lang="en")
    tts.save("temp.mp3")

    # Measure the speech duration using pydub
    full_audio = AudioSegment.from_file("temp.mp3")
    full_audio_duration = len(full_audio) / 1000  # duration in seconds
    avg_word_duration = full_audio_duration / len(words)  # average duration per word

    # Initialize background index and duration tracker
    current_background_index = 0
    background_change_time = BACKGROUND_INTERVALS[current_background_index]
    image_duration = 0

    for i, word in enumerate(words):
        # Change background image based on interval
        if image_duration >= background_change_time:
            current_background_index = (current_background_index + 1) % len(background_images)
            if current_background_index < len(BACKGROUND_INTERVALS):
                background_change_time += BACKGROUND_INTERVALS[current_background_index]
            image_duration = 0

        # Load the current background image
        bg_img = Image.open(background_images[current_background_index]).resize(VIDEO_SIZE)

        # Calculate text size and position using getbbox
        text_bbox = fnt.getbbox(word)
        text_width, text_height = text_bbox[2] - text_bbox[0], text_bbox[3] - text_bbox[1]
        position = ((VIDEO_SIZE[0] - text_width) / 2, (VIDEO_SIZE[1] - text_height) / 2)

        # Create a new image with the background
        img = bg_img.copy()
        d = ImageDraw.Draw(img)
        d.text(position, word, font=fnt, fill=TEXT_COLOR)

        images.append(np.array(img))
        durations.append(avg_word_duration)  # Set frame duration based on average word duration

        image_duration += avg_word_duration  # Increment image duration

    audioclip = AudioFileClip("temp.mp3")
    clip = ImageSequenceClip(images, durations=durations)
    clip = clip.set_audio(audioclip)

    clip.fps = TEXT_SPEED
    clip.write_videofile(outputfile, codec="libx264")

    # Remove the temporary file
    os.remove("temp.mp3")

@app.route("/", methods=["GET", "POST"])
def upload_file():
    if request.method == "POST":
        # Check if the files are present
        if 'text_file' not in request.files or 'font_file' not in request.files or 'images[]' not in request.files:
            return 'Missing files', 400
        
        # Get the files from the request
        text_file = request.files['text_file']
        font_file = request.files['font_file']
        image_files = request.files.getlist('images[]')

        # Save the text file
        if text_file and allowed_file(text_file.filename):
            text_filename = secure_filename(text_file.filename)
            text_content = text_file.read().decode("utf-8")

        # Save the font file
        if font_file and allowed_file(font_file.filename):
            font_filename = secure_filename(font_file.filename)
            font_path = os.path.join(app.config['UPLOAD_FOLDER'], font_filename)
            font_file.save(font_path)

        # Save image files
        background_images = []
        for image in image_files:
            if image and allowed_file(image.filename):
                image_filename = secure_filename(image.filename)
                image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
                image.save(image_path)
                background_images.append(image_path)

        # Generate the video
        output_filename = f"{uuid.uuid4().hex}.mp4"
        text_to_video(text_content, font_path, background_images, output_filename)

        # Redirect to download the video
        return redirect(url_for("download_file", filename=output_filename))

    return '''
    <!doctype html>
    <title>Upload Files</title>
    <h1>Upload Text, Font, and Background Images</h1>
    <form method=post enctype=multipart/form-data>
      <label for="text_file">Text File:</label>
      <input type="file" name="text_file" accept=".txt" required><br><br>
      <label for="font_file">Font File:</label>
      <input type="file" name="font_file" accept=".ttf" required><br><br>
      <label for="images">Background Images:</label>
      <input type="file" name="images[]" accept=".png,.jpg,.jpeg" multiple required><br><br>
      <input type=submit value=Upload>
    </form>
    '''

@app.route("/download/<filename>")
def download_file(filename):
    return send_file(filename, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)
