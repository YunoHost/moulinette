import threading
import Queue


# Read from a stream ---------------------------------------------------

class AsynchronousFileReader(threading.Thread):
    """
    Helper class to implement asynchronous reading of a file
    in a separate thread. Pushes read lines on a queue to
    be consumed in another thread.

    Based on:
    http://stefaanlippens.net/python-asynchronous-subprocess-pipe-reading

    """
    def __init__(self, fd, queue):
        assert isinstance(queue, Queue.Queue)
        assert callable(fd.readline)
        threading.Thread.__init__(self)
        self._fd = fd
        self._queue = queue

    def run(self):
        """The body of the tread: read lines and put them on the queue."""
        for line in iter(self._fd.readline, ''):
            self._queue.put(line)

    def eof(self):
        """Check whether there is no more content to expect."""
        return not self.is_alive() and self._queue.empty()

    def join(self, timeout=None, close=True):
        """Close the file and join the thread."""
        if close:
            self._fd.close()
        threading.Thread.join(self, timeout)


def start_async_file_reading(fd):
    """Helper which instantiate and run an AsynchronousFileReader."""
    queue = Queue.Queue()
    reader = AsynchronousFileReader(fd, queue)
    reader.start()
    return (reader, queue)
