from datetime import datetime
import multiprocessing as mp
import time
import queue
import threading
import subprocess
import logging
from bson.objectid import ObjectId

from database import Database

logger = logging.getLogger('demucs-frontend')

def worker_process(q):
    logger.info('Worker process started')

    db = Database()

    def enqueue_output(out, q):
        read_size = 128
        for data in iter(lambda: out.read(read_size), b''):
            q.put(data)
        out.close()

    while True:
        job_id = q.get()

        logger.info('Worker starting to process {}'.format(job_id))

        db.jobs_collection.find_one_and_update({'_id': ObjectId(job_id)}, {'$set': {
            'status': 'processing'
        }})

        args = ['bash', '../demucs-frontend/demucs_run.sh', job_id]

        logger.info('Args: {}'.format(' '.join(args)))
        process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd='../demucs/')
        output_queue = mp.Queue()
        output_bytes = b''

        thread = threading.Thread(target=enqueue_output, args=(process.stdout, output_queue,))
        thread.daemon = True
        thread.start()
        
        start_time = datetime.now()
        while True:
            try:
                while True:
                    line = output_queue.get_nowait()
                    output_bytes += line
            except queue.Empty:
                pass

            if process.poll() is not None:
                break

            current_time = datetime.now()
            duration = (current_time - start_time).total_seconds()
            if duration >= 600:
                process.kill()
                break

            time.sleep(0.5)

        while not output_queue.empty():
            data = output_queue.get()
            output_bytes += data

        output_str = output_bytes.decode('utf-8').replace('\r', '\n')

        logger.info('ID={} Done, ret code={}'.format(job_id, process.returncode))

        if process.returncode == 0:
            db.jobs_collection.find_one_and_update({'_id': ObjectId(job_id)}, {'$set': {
                'status': 'done',
                'output': output_str
            }})
        else:
            db.jobs_collection.find_one_and_update({'_id': ObjectId(job_id)}, {'$set': {
                'status': 'error',
                'output': output_str
            }})