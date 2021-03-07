from pymongo import MongoClient

class Database():
    def __init__(self):
        self.client = MongoClient()
        self.db = self.client['demucs']
        self.jobs_collection = self.db['jobs']
        