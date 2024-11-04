from flask import Flask, render_template, request, redirect, url_for, send_from_directory
import os
import base64
from iptcinfo3 import IPTCInfo
from openai import OpenAI
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = 'your_secret_key'

app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['FINAL_IMAGE_FOLDER'] = 'processed'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['FINAL_IMAGE_FOLDER'], exist_ok=True)


# define openAI Client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Utility function to save the uploaded image and return its path
def save_image(file):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(file_path)
    return file_path

# Utility function to get base64-encoded string of an image
def get_base64_encoding(file_path):
    with open(file_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")

# Generate caption and Search Keywords
def generate_caption(imageEncoded):
    response = client.chat.completions.create(
        model="gpt-4o",
        messages= [
            {
                "role":"user",
                "content": [
                    { "type": "text", "text": "Please generate caption and 50 search keywords separated by commas for the given image in python dictionary format without python tag."},
                    { "type": "image_url", "image_url": {
                        "url": f"data:image/jpeg;base64,{imageEncoded}"
                    }},
                ]
            }
        ]
    )
    return response

# Utility function to save base64-encoded string as metadata
def add_metadata(file_path, file_name, caption, keywords):
    # print(f"add_metadata: \n file_path: {file_path} \n file_name: {file_name}")
    
    # Open the image and update the metadata information
    iptc_info = IPTCInfo(file_path)
    iptc_info['caption/abstract'] = caption
    iptc_info['keywords'] = [keywords]
    iptc_info['object name'] = caption

    # define the output directory and save the updated image in processed folder
    destination_file_name = os.path.join(app.config['FINAL_IMAGE_FOLDER'], file_name)
    iptc_info.save_as(destination_file_name)

    return f"Image Metadata updated Successfully for the image{file_name}"

# Route to serve images from the 'uploads' folder
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    # Serve the file from the 'uploads' directory
    return send_from_directory('uploads', filename)


# Route to display and upload images
@app.route("/", methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        files = request.files.getlist("images")
        file_paths = [save_image(file) for file in files]
        return redirect(url_for('display_images'))
    return render_template("index.html")


# Route to display uploaded images
@app.route("/display", methods=['GET', 'POST'])
def display_images():
    if request.method == 'POST':
        # Get the image path and metadata from the form
        file_name = request.form.get("file_name")
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file_name)

        # check the requested action and if generate - Generate the caption and Keywords for the given image
        if request.form.get("action") == "generate":
            base64_str = get_base64_encoding(file_path)
            ai_response = generate_caption(base64_str)
            ai_response_json = json.loads(ai_response.choices[0].message.content)
            caption_generated = ai_response_json["caption"]
            keywords_generated = ai_response_json["keywords"]
            return {"caption_generated": caption_generated, "keywords_generated": keywords_generated}
        
        # check the requested action and if save - Save the caption and Keywords generated to image metadata
        elif request.form.get("action") == "save":
            caption = request.form["caption"]
            keywords = request.form["keywords"]
            response = add_metadata(file_path, file_name, caption, keywords)
            os.remove(file_path) 
            return response
    
    images = []
    print(f"Directory Contents: {os.listdir(app.config['UPLOAD_FOLDER'])}")
    #  check if upload directory is empty and redirect to upload page
    if len(os.listdir(app.config['UPLOAD_FOLDER'])) == 0:
        return redirect(url_for('index'))
    
    for filename in os.listdir(app.config['UPLOAD_FOLDER']):
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file_url = url_for('uploaded_file', filename=filename)
        # print(f"** file_path: {file_path}, file_name: {filename}")
        images.append({"path": file_url, "filename": filename, })
    return render_template("display.html", images=images)

if __name__ == "__main__":
    app.run(debug=True)