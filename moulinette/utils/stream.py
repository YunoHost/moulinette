import os
import time

from multiprocessing.process import Process
from multiprocessing.queues import SimpleQueue


# Read from a stream ---------------------------------------------------


class AsynchronousFileReader(Process):

    """
    Helper class to implement asynchronous reading of a file
    in a separate thread. Pushes read lines on a queue to
    be consumed in another thread.

    Based on:
    http://stefaanlippens.net/python-asynchronous-subprocess-pipe-reading

    """

    def __init__(self, fd, queue):
        assert hasattr(queue, "put")
        assert hasattr(queue, "empty")
        assert isinstance(fd, int) or callable(fd.readline)
        Process.__init__(self)
        self._fd = fd
        self._queue = queue

    def run(self):
        """The body of the tread: read lines and put them on the queue."""

        # If self._fd is a file opened with open()...
        # Typically that's for stdout/stderr pipes
        # We can read the stuff easily with 'readline'
        if not isinstance(self._fd, int):
            for line in iter(self._fd.readline, ""):
                self._queue.put(line)

        # Else, it got opened with os.open() and we have to read it
        # wit low level crap...
        else:
            data = ""
            while True:
                # Try to read (non-blockingly) a few bytes, append them to
                # the buffer
                data += os.read(self._fd, 50)

                # If nobody's writing in there anymore, get out
                if not data and os.fstat(self._fd).st_nlink == 0:
                    return

                # If we have data, extract a line (ending with \n) and feed
                # it to the consumer
                if data and "\n" in data:
                    lines = data.split("\n")
                    self._queue.put(lines[0])
                    data = "\n".join(lines[1:])
                else:
                    time.sleep(0.05)

    def eof(self):
        """Check whether there is no more content to expect."""
        return not self.is_alive() and self._queue.empty()

    def join(self, timeout=None, close=True):
        """Close the file and join the thread."""
        if close:
            self._queue.put(StopIteration)
            if isinstance(self._fd, int):
                os.close(self._fd)
            else:
                self._fd.close()
        Process.join(self, timeout)


class Consummer(object):
    def __init__(self, queue, callback):
        self.queue = queue
        self.callback = callback

    def empty(self):
        return self.queue.empty()

    def process_next_line(self):
        if not self.empty():
            line = self.queue.get()
            if line:
                if line == StopIteration:
                    return
                self.callback(line)

    def process_current_queue(self):
        while not self.empty():
            line = self.queue.get()
            if line:
                if line == StopIteration:
                    break
                self.callback(line)


def async_file_reading(fd, callback):
    """Helper which instantiate and run an AsynchronousFileReader."""
    queue = SimpleQueue()
    reader = AsynchronousFileReader(fd, queue)
    reader.start()
    consummer = Consummer(queue, callback)
    return (reader, consummer)
