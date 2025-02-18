import os
from tinydb import TinyDB


def ensure_db(file_name):
    if not os.path.exists('./db'):
        os.makedirs('./db')
    path_name = os.path.join('./db', file_name)
    if not os.path.exists(path_name):
        with open(path_name, mode='w+') as f:
            f.write('')
    db = TinyDB(path_name)
    return db


def ensure_folder(dir):
    dir_path = os.path.join('./', dir)
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
        return 1
    return 0
