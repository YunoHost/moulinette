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
        assert hasattr(queue, 'put')
        assert hasattr(queue, 'empty')
        assert callable(fd.readline)
        Process.__init__(self)
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
            self._queue.put(StopIteration)
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
