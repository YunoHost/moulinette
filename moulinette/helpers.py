# -*- coding: utf-8 -*-

from threading import Thread
from Queue import Queue, Empty

class NonBlockingStreamReader:
    """A non-blocking stream reader

    Open a separate thread which reads lines from the stream whenever data
    becomes available and stores the data in a queue.

    Based on: http://eyalarubas.com/python-subproc-nonblock.html

    Keyword arguments:
        - stream -- The stream to read from

    """
    def __init__(self, stream):
        self._s = stream
        self._q = Queue()

        def _populateQueue(stream, queue):
            """Collect lines from the stream and put them in the queue"""
            while True:
                line = stream.readline()
                if line:
                    queue.put(line)
                else:
                    break

        self._t = Thread(target=_populateQueue, args=(self._s, self._q))
        self._t.daemon = True
        # Start collecting lines from the stream
        self._t.start()

    def readline(self, block=False, timeout=None):
        """Read line from the stream

        Attempt to pull from the queue the data and return it. If no data is
        available or timeout has expired, it returns None.

        Keyword arguments:
            - block -- If True, block if necessary until data is available
            - timeout -- The number of seconds to block

        """
        try:
            return self._q.get(block=timeout is not None,
                    timeout=timeout)
        except Empty:
            return None

    def close(self):
        """Close the stream"""
        try:
            self._s.close()
        except IOError:
            pass
