import tempfile
from flask import Flask, request, jsonify, send_file, render_template
from pathlib import Path
from werkzeug.utils import secure_filename
import subprocess
import requests


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
        return jsonify({'error': 'No file part'}), 400  # Bad Request

    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400  # Bad Request

    if allowed_file(file.filename):
        filename = secure_filename(file.filename)
    else:
        return jsonify({'error': 'Wrong extension', 'allowed_extensions': allowed_extensions}), 400  # Bad Request

    with tempfile.TemporaryDirectory(dir=UPLOAD_FOLDER) as random_temp_subfolder:
        file_path = Path(random_temp_subfolder, filename)
        file.save(file_path)
        print(f'Uploaded file saved: {file_path=}')

        converted_file_path = convert_file(file_path)
        if converted_file_path:
            print(f'Converted to: {converted_file_path}')
            return send_file(converted_file_path, as_attachment=True, download_name=converted_file_path.name), 200
        else:
            return jsonify({'error': 'Converted file not found'}), 404  # Not Found


@app.route('/status', methods=['GET'])
def check_status():
    return jsonify({'status': 'ok'}), 200


@app.route('/api_test')
def api_test():
    allowed_extensions_string = ', '.join(allowed_extensions)
    return render_template('api_test.html', allowed_extensions_string=allowed_extensions_string)


api_endpoint = 'http://127.0.0.1:5000/convertfile'

@app.route('/api_test_form', methods=['GET', 'POST'])
def api_test_form():
    allowed_extensions_string = ', '.join(allowed_extensions)
    if request.method == 'POST':
        file = request.files.get('file')

        if not file:
            return render_template(
                'api_test_form.html',
                error_message='No file selected',
                allowed_extensions_string=allowed_extensions_string
            )

        # Save the uploaded file to the temporary directory
        temp_upload_folder = UPLOAD_FOLDER
        temp_upload_folder.mkdir(parents=True, exist_ok=True)

        temp_file_path = temp_upload_folder / file.filename
        file.save(temp_file_path)
        print(f'Saved file: {temp_file_path}')
        try:
            # Make a request to the API endpoint with the uploaded file
            api_response = requests.post(api_endpoint, files={'file': (file.filename, open(temp_file_path, 'rb'))})
            print(f'{api_response=}')

            # Check if the API request was successful (status code 200)
            if api_response.status_code == 200:
                # Save the API response file to another temporary directory
                temp_response_folder = Path.cwd() / 'temp_response'
                temp_response_folder.mkdir(parents=True, exist_ok=True)

                temp_response_file_path = temp_response_folder / file.filename
                with open(temp_response_file_path, 'wb') as response_file:
                    response_file.write(api_response.content)

                # Render the HTML page with success message and link to download the response file
                return render_template('api_test_form.html', success_message='API request successful',
                                       api_response_headers=api_response.headers,
                                       download_link=f'/download_response/{file.filename}',
                                       allowed_extensions_string=allowed_extensions_string
                                       )

            else:
                # Render the HTML page with error message and API response status code
                return render_template('api_test_form.html',
                                       error_message=f'API request failed (Status Code: {api_response.status_code})',
                                       allowed_extensions_string=allowed_extensions_string
                                       )

        except requests.RequestException as e:
            # Render the HTML page with error message if the API request encounters an exception
            return render_template('api_test_form.html',
                                   error_message=f'API request failed: {str(e)}',
                                   allowed_extensions_string=allowed_extensions_string
                                   )

    # Render the initial HTML page for GET requests
    return render_template('api_test_form.html',
                           allowed_extensions_string=allowed_extensions_string
                           )


if __name__ == '__main__':
    app.run(debug=True, port=5000)
