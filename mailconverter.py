import tempfile
from flask import Flask, request, jsonify, send_file, render_template, url_for
from pathlib import Path
from werkzeug.utils import secure_filename
import subprocess
import requests
import shutil
import json
import os

app = Flask(__name__)

TEMP_UPLOAD_FOLDER = Path.cwd() / 'temp_uploads'
TEMP_UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
# Save the API response file to another temporary directory
TEMP_REPONSE_FOLDER = Path.cwd() / 'temp_response'
TEMP_REPONSE_FOLDER.mkdir(parents=True, exist_ok=True)
DOWNLOAD_RESPONSE_URL = '/download_response/'

app.config['UPLOAD_FOLDER'] = TEMP_UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # Limit file size to 200 MB
allowed_extensions = {'.msg', '.eml'}
convert_to_extension = '.pdf'
wine_path = 'wine'
converter_path = './MailConverter.exe'

current_directory = os.getcwd()


def clear_folder(folder_path):
    folder_path = Path(folder_path)
    if folder_path.is_dir():
        # Use shutil.rmtree to remove the entire directory and its contents
        shutil.rmtree(folder_path)
        folder_path.mkdir(parents=True, exist_ok=True)
        print(f"Cleared and recreated the folder: {folder_path}")
    else:
        print(f"Folder '{folder_path}' does not exist.")


def allowed_file(filename):
    return Path(filename).suffix.lower() in allowed_extensions


def convert_file(original_file_path):
    # Ensure the input file exists
    original_path = Path(original_file_path)
    print(f'\t{original_file_path} {str(original_path)}')
    if not original_path.is_file():
        return None  # File not found

    converted_file_path = original_path.with_suffix(convert_to_extension)
    # subprocess.run([converter_path, str(original_path), str(converted_file_path)])
    try:
        print('Running:', wine_path, converter_path, str(original_path), str(converted_file_path))
        subprocess.run([wine_path, converter_path, original_path, converted_file_path], check=True)
        print(f'\tIn convert_file: {str(original_path)=}, {str(converted_file_path)}, {str(converted_file_path.is_file())}')

    except Exception as e:
        print(f'Error while running converter {e}')
        return None

    return converted_file_path


@app.route('/convertfile', methods=['POST'])
def upload_and_convert_file():
    file = request.files.get('file')

    if not file:
        return jsonify({'error': 'No file part'}), 401  # Bad Request

    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 402  # Bad Request

    if allowed_file(file.filename):
        filename = secure_filename(file.filename)
    else:
        return jsonify({'error': 'Wrong extension', 'allowed_extensions': allowed_extensions}), 403  # Bad Request

    with tempfile.TemporaryDirectory(dir=TEMP_UPLOAD_FOLDER) as random_temp_subfolder:
        file_path = Path(random_temp_subfolder, filename)
        file.save(file_path)
        print(f'Uploaded file saved: {file_path=}')

        relative_file_path = file_path.relative_to(current_directory)
        # relative_output_file_path = output_file_path.relative_to(current_directory)

        converted_file_path = convert_file(relative_file_path)
        print(f'Get converted result in: {converted_file_path}, is file: {converted_file_path.is_file()}')
        if converted_file_path:
            return send_file(converted_file_path, as_attachment=True, download_name=converted_file_path.name), 200
        else:
            return jsonify({'error': 'Converted while converter run.'}), 404  # Not Found

@app.route('/status', methods=['GET'])
def check_status():
    return jsonify({'status': 'ok'}), 200


# @app.route('/api_test')
# def api_test():
#     allowed_extensions_string = ', '.join(allowed_extensions)
#     return render_template('api_test.html', allowed_extensions_string=allowed_extensions_string)


# api_endpoint = 'http://127.0.0.1:5000/convertfile'
# api_endpoint = f'http://{get_own_url()}:5000/convertfile'
# curl -X POST -F "file=@./mail.eml" http://localhost:5000/convertfile

@app.route('/api_test_form', methods=['GET', 'POST'])
def api_test_form():
    url_root = request.url_root
    api_endpoint = f"{url_root}convertfile"
    allowed_extensions_string = ', '.join(allowed_extensions)
    if request.method == 'POST':
        file = request.files.get('file')

        if not file:
            return render_template(
                'api_test_form.html',
                api_endpoint=api_endpoint,
                error_message='No file selected',
                allowed_extensions_string=allowed_extensions_string
            )

        temp_upload_folder = TEMP_UPLOAD_FOLDER
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
                # Extract the filename from the Content-Disposition header
                content_disposition = api_response.headers.get('Content-Disposition', '')
                converted_filename = content_disposition.replace('attachment; filename=', '').strip('"')

                temp_response_file_path = TEMP_REPONSE_FOLDER / converted_filename
                with open(temp_response_file_path, 'wb') as response_file:
                    response_file.write(api_response.content)

                try:
                    formatted_api_response_headers = json.dumps(dict(api_response.headers), indent=4)
                except Exception as _:
                    print(f'Error to prettify with {_}, {api_response.headers=}')
                    formatted_api_response_headers = api_response.headers

                return render_template('api_test_form.html',
                                       success_message=f'API request successful, status code: {api_response.status_code}',
                                       api_endpoint=api_endpoint,
                                       api_response_headers=formatted_api_response_headers,
                                       download_link=f'{DOWNLOAD_RESPONSE_URL}{converted_filename}',
                                       download_filename=f'{converted_filename}',
                                       allowed_extensions_string=allowed_extensions_string
                                       )

            else:
                return render_template('api_test_form.html',
                                       api_endpoint=api_endpoint,
                                       error_message=f'API request failed (Status Code: {api_response.status_code})',
                                       allowed_extensions_string=allowed_extensions_string
                                       )

        except requests.RequestException as e:
            # Render the HTML page with error message if the API request encounters an exception
            return render_template('api_test_form.html',
                                   api_endpoint=api_endpoint,
                                   error_message=f'API request failed: {str(e)}',
                                   allowed_extensions_string=allowed_extensions_string
                                   )

    # Render the initial HTML page for GET requests
    return render_template('api_test_form.html',
                           api_endpoint = api_endpoint,
                           allowed_extensions_string=allowed_extensions_string
                           )


@app.route(f'{DOWNLOAD_RESPONSE_URL}<filename>')
def download_response(filename):
    temp_response_file_path = TEMP_REPONSE_FOLDER / filename
    if temp_response_file_path.is_file():
        return send_file(temp_response_file_path, as_attachment=True, download_name=filename)
    else:
        return render_template('api_test_form.html', error_message='Downloaded file not found')



if __name__ == '__main__':
    clear_folder(TEMP_REPONSE_FOLDER)
    clear_folder(TEMP_UPLOAD_FOLDER)
    #app.run(host='0.0.0.0', debug=True, port=5000)
    app.run(host='0.0.0.0', port=5000)