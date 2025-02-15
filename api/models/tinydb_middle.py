from tinydb import TinyDB
from tinydb.middlewares import Middleware
import fcntl

# 自定义中间件
class LockingMiddleware(Middleware):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.file = open('db.json', 'r+')

    def read(self):
        fcntl.flock(self.file, fcntl.LOCK_SH)  # 加共享锁
        data = self.file.read()
        fcntl.flock(self.file, fcntl.LOCK_UN)  # 解锁
        return data

    def write(self, data):
        fcntl.flock(self.file, fcntl.LOCK_EX)  # 加独占锁
        self.file.seek(0)
        self.file.write(data)
        self.file.truncate()
        fcntl.flock(self.file, fcntl.LOCK_UN)  # 解锁
