import os
import tempfile

class MyJiraLog:
    def __init__(self):
        self.server = os.getenv('LOGSERVER')
        self.user = os.getenv('LOGUSER')

    def get_log(self):
        self.tempfile = tempfile.NamedTemporaryFile(delete=False)
        log_path = f'{self.user}@{self.server}:~/sprint-snapshot.log'
        os.system(f'scp {log_path} {self.tempfile.name} > /dev/null 2>&1')
        if os.stat(self.tempfile.name).st_size == 0:
            os.unlink(self.tempfile.name)
            raise Exception('Log file is empty, failed to retrieve log file from server.')

        return self.tempfile.name


