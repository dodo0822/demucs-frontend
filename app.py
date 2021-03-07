from flask import Flask, render_template, request
from flask.helpers import send_file
from werkzeug.utils import secure_filename
from bson.objectid import ObjectId

import multiprocessing as mp
import datetime
import os
import logging
import pymongo
import zipfile
from io import BytesIO

from worker import worker_process
from database import Database

BASE_PATH = os.path.dirname(os.path.realpath(__file__))
UPLOAD_PATH = os.path.join(BASE_PATH, 'input/')
OUTPUT_PATH = os.path.join(BASE_PATH, 'output', 'demucs')
ALLOWED_EXTENSIONS = {'mp3'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

logger = logging.getLogger('demucs-frontend')
logger.setLevel(logging.DEBUG)

ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)

logger.addHandler(ch)

app = Flask(__name__)
q = mp.Queue()

@app.route('/')
def home():
    jobs = app.db.jobs_collection.find({}, sort=[('create_time', pymongo.DESCENDING)])
    return render_template('index.html', jobs=jobs)

@app.route('/details')
def details():
    if 'id' not in request.args:
        return render_template('details.html', error='Invalid request')
    job_id = request.args['id']
    job = app.db.jobs_collection.find_one({'_id': ObjectId(job_id)})
    if job is None:
        return render_template('details.html', error='Job not found')
    return render_template('details.html', job=job)

@app.route('/download')
def download():
    if 'id' not in request.args:
        return 'Invalid request'
    job_id = request.args['id']
    job = app.db.jobs_collection.find_one({'_id': ObjectId(job_id)})
    if job is None:
        return 'Job is not found'
    if job['status'] != 'done':
        return 'Job is not done yet'

    output_dir = os.path.join(OUTPUT_PATH, str(job['_id']))
    if not os.path.isdir(output_dir):
        return 'Error: output file not found!'
    
    download_file = job['filename'] + '_separated.zip'
    try:
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(output_dir):
                for file in files:
                    zf.write(os.path.join(root, file),
                             os.path.relpath(os.path.join(root, file),
                                             os.path.join(output_dir, '..')))
        buffer.seek(0)
        return send_file(buffer, attachment_filename=download_file, as_attachment=True)
    except Exception as e:
        logger.warn('Exception when zipping file: {}'.format(e))
        return 'Error: could not zip file'

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return render_template('upload.html', message='File not present!')

    file = request.files['file']
    if file.filename == '':
        return render_template('upload.html', message='No selected file!')

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        job = {
            'filename': filename,
            'create_time': datetime.datetime.utcnow(),
            'status': 'wait',
            'log': ''
        }
        job_id = app.db.jobs_collection.insert_one(job).inserted_id
        logger.info('Job received with id={} and filename={}'.format(job_id, filename))

        file.save(os.path.join(UPLOAD_PATH, '{}.mp3'.format(job_id)))
        q.put(str(job_id))
        return render_template('upload.html', message='File uploaded and enqueued!')

    return render_template('upload.html', message='File type is not allowed!')

if __name__ == '__main__':
    p = mp.Process(target=worker_process, args=(q,))
    p.start()
    app.db = Database()
    app.db.jobs_collection.update_many({'$or':[{'status': 'wait'}, {'status': 'processing'}]}, {'$set': {'status': 'cancel'}})
    app.run(host='0.0.0.0')