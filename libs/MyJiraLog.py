import os
import tempfile
import subprocess
import datetime

class MyJiraLog:
    def __init__(self):
        self.server = os.getenv('LOGSERVER')
        self.user = os.getenv('LOGUSER')

    def parse_date(self, line):
        try:
            date_time = line.split(',')[0]
            date = date_time.split(' ')[0]
            day, month, year = date.split('/')
            date_of_line = datetime.datetime(int(year), int(month), int(day))
            return date_of_line
        except:
            return None

    def get_log(self, time_period = 14):
        self.tempfile = tempfile.NamedTemporaryFile(delete=False)
        log_path = f'{self.user}@{self.server}:~/sprint-snapshot.log'
        process = subprocess.Popen(['scp', log_path, self.tempfile.name], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        process.wait()

        if os.stat(self.tempfile.name).st_size == 0:
            os.unlink(self.tempfile.name)
            raise Exception('Log file is empty, failed to retrieve log file from server.')

        # Calculate today - time_period
        today = datetime.datetime.now()
        n_days_ago = datetime.timedelta(days=time_period)
        too_old = today - n_days_ago

        # Filter out lines older than n_days_ago
        filtered_lines = []
        with open(self.tempfile.name, 'r') as f:
            lines = f.readlines()
            for i, line in enumerate(lines):
                date_of_line = self.parse_date(line)
                if date_of_line is None or date_of_line > too_old:
                    filtered_lines.append(line)

        with open(self.tempfile.name, 'w') as f:
            f.writelines(filtered_lines)

        return self.tempfile.name


