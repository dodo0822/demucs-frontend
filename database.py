from pymongo import MongoClient

import config

class Database():
    def __init__(self):
        self.client = MongoClient(config.db_host, config.db_port)
        self.db = self.client['demucs']
        self.jobs_collection = self.db['jobs']
        