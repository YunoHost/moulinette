import os
import threading

class LogPipe(threading.Thread):
    # Adapted from https://codereview.stackexchange.com/a/17959
    def __init__(self, log_callback, queue):
        """Setup the object with a logger and a loglevel
        and start the thread
        """
        threading.Thread.__init__(self)
        self.daemon = False
        self.log_callback = log_callback

        self.fdRead, self.fdWrite = os.pipe()
        self.pipeReader = os.fdopen(self.fdRead)

        self.queue = queue

        self.start()

    def fileno(self):
        """Return the write file descriptor of the pipe"""
        return self.fdWrite

    def run(self):
        """Run the thread, logging everything."""
        for line in iter(self.pipeReader.readline, ""):
            self.queue.put((self.log_callback, line.strip("\n")))

        self.pipeReader.close()

    def close(self):
        """Close the write end of the pipe."""
        os.close(self.fdWrite)


