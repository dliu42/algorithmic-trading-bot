import sys

class DualLogger:
    def __init__(self, filename):
        self.terminal = sys.stdout
        self.log = open(filename, "a", encoding='utf-8')

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)

    def flush(self):
        self.terminal.flush()
        self.log.flush()

    @staticmethod
    def setup_logging(log_dir="../logs"):
        """Sets up logging to file and returns the filename."""
        import os
        from datetime import datetime
        
        if not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(log_dir, f"{timestamp}.txt")
        
        # Redirect stdout to both terminal and file
        sys.stdout = DualLogger(log_file)
        print(f"Logging output to: {log_file}")
        return log_file
