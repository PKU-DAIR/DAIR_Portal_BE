import os


def ensure_folder(dir_name):
    dir_path = os.path.join('./', dir_name)
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
        return 1
    return 0
