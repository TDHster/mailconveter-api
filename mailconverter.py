import tempfile
from flask import Flask, request, jsonify, send_file, render_template
from pathlib import Path
from werkzeug.utils import secure_filename
import subprocess


app = Flask(__name__)


UPLOAD_FOLDER = Path.cwd() / 'temp_uploads'
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # Limit file size to 200 MB
allowed_extensions = {'.msg', '.eml'}
convert_to_extension = '.pdf'
wine_path = 'wine'
converter_path = 'cp'

def allowed_file(filename):
    return Path(filename).suffix.lower() in allowed_extensions


def convert_file(original_file_path):
    # Ensure the input file exists
    original_path = Path(original_file_path)
    if not original_path.is_file():
        return None  # File not found
    converted_file_path = original_path.with_suffix(convert_to_extension)
    subprocess.run([converter_path, str(original_path), str(converted_file_path)])
    # subprocess.run([wine_path, converter_path, str(original_path), str(converted_file_path)])

    return converted_file_path


@app.route('/convertfile', methods=['POST'])
def upload_file():
    file = request.files.get('file')

    if not file:
        return jsonify({'error': 'No file part'})

    if file.filename == '':
        return jsonify({'error': 'No selected file'})

    if allowed_file(file.filename):
        filename = secure_filename(file.filename)
    else:
        return jsonify({'error': 'Wrong extension', 'allowed_extensions': allowed_extensions})

    with tempfile.TemporaryDirectory(dir=UPLOAD_FOLDER) as random_temp_subfolder:
        file_path = Path(random_temp_subfolder, filename)
        file.save(file_path)
        print(f'Uploaded file saved: {file_path=}')

        converted_file_path = convert_file(file_path)
        if converted_file_path:
            print(f'Converted to: {converted_file_path}')
        else:
            print('Original file not found while running convert function.')

        # Send API answer
        if converted_file_path.is_file():
            print(f'Sending answer with {converted_file_path}')
            return send_file(converted_file_path, as_attachment=True, download_name=converted_file_path.name)
        else:
            return jsonify({'error': 'Converted file not found'})


@app.route('/status', methods=['GET'])
def check_status():
    return jsonify({'status': 'ok'})


@app.route('/api_test')
def api_test_form():
    return render_template('api_test.html', allowed_extensions=allowed_extensions)


if __name__ == '__main__':
    app.run(debug=True, port=5000)
