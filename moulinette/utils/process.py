import subprocess
import os
import threading
import queue
import logging

# This import is unused in this file. It will be deleted in future (W0611 PEP8),
# but for the momment we keep it due to yunohost moulinette script that used
# process.quote syntax to access this module !
from shlex import quote

quote  # This line is here to avoid W0611 PEP8 error (see comments above)

# Prevent to import subprocess only for common classes
CalledProcessError = subprocess.CalledProcessError
logger = logging.getLogger("moulinette.utils.process")

# Alternative subprocess methods ---------------------------------------


def check_output(args, stderr=subprocess.STDOUT, shell=True, **kwargs):
    """Run command with arguments and return its output as a byte string

    Overwrite some of the arguments to capture standard error in the result
    and use shell by default before calling subprocess.check_output.

    """
    return (
        subprocess.check_output(args, stderr=stderr, shell=shell, **kwargs)
        .decode("utf-8")
        .strip()
    )


# Call with stream access ----------------------------------------------


def call_async_output(args, callback, **kwargs):
    """Run command and provide its output asynchronously

    Run command with arguments and wait for it to complete to return the
    returncode attribute. The `callback` can be a method or a 2-tuple of
    methods - for stdout and stderr respectively - which must take one
    byte string argument. It will be called each time the command produces
    some output.

    The stdout and stderr additional arguments for the Popen constructor
    are not allowed as they are used internally.

    Keyword arguments:
        - args -- String or sequence of program arguments
        - callback -- Method or object to call with output as argument
        - kwargs -- Additional arguments for the Popen constructor

    Returns:
        Exit status of the command

    """
    for a in ["stdout", "stderr"]:
        if a in kwargs:
            raise ValueError("%s argument not allowed, " "it will be overridden." % a)

    log_queue = queue.Queue()

    kwargs["stdout"] = LogPipe(callback[0], log_queue)
    kwargs["stderr"] = LogPipe(callback[1], log_queue)
    stdinfo = LogPipe(callback[2], log_queue) if len(callback) >= 3 else None
    if stdinfo:
        kwargs["pass_fds"] = [stdinfo.fdWrite]
        if "env" not in kwargs:
            kwargs["env"] = os.environ
        kwargs["env"]["YNH_STDINFO"] = str(stdinfo.fdWrite)

    if "env" in kwargs and not all(isinstance(v, str) for v in kwargs["env"].values()):
        logger.warning(
            "While trying to call call_async_output: env contained non-string values, probably gonna cause issue in Popen(...)"
        )

    try:
        p = subprocess.Popen(args, **kwargs)

        while p.poll() is None:
            while True:
                try:
                    callback, message = log_queue.get(True, 0.1)
                except queue.Empty:
                    break

                callback(message)
        while True:
            try:
                callback, message = log_queue.get_nowait()
            except queue.Empty:
                break

            callback(message)
    finally:
        kwargs["stdout"].close()
        kwargs["stderr"].close()
        if stdinfo:
            stdinfo.close()

    return p.poll()


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
        self.pipeReader = os.fdopen(self.fdRead, "rb")

        self.queue = queue

        self.start()

    def fileno(self):
        """Return the write file descriptor of the pipe"""
        return self.fdWrite

    def run(self):
        """Run the thread, logging everything."""
        for line in iter(self.pipeReader.readline, b""):
            self.queue.put((self.log_callback, line.decode("utf-8").strip("\n")))

        self.pipeReader.close()

    def close(self):
        """Close the write end of the pipe."""
        os.close(self.fdWrite)


# Call multiple commands -----------------------------------------------


def run_commands(cmds, callback=None, separate_stderr=False, shell=True, **kwargs):
    """Run multiple commands with error management

    Run a list of commands and allow to manage how to treat errors either
    with raise_on_error or callback arguments.

    If callback is provided, it will be called when the command returns
    a non-zero exit code. The callback must take 3 arguments; the
    returncode, the command which failed and the command output. The
    callback should return either False to stop commands execution or True
    to continue.
    Otherwise, if raise_on_error is True a CalledProcessError exception will
    be raised when a command returns a non-zero exit code.

    If callback is provided or raise_on_error is False, all commands will
    be executed and the number of failed commands will be returned.

    The standard output and error of a failed command can be separated with
    separate_stderr set to True. In that case, the output argument passed to
    the callback or the output attribute of the CalledProcessError exception
    will be a 2-tuple containing stdout and stderr as byte strings.

    Keyword arguments:
        - cmds -- List of commands to run
        - callback -- Method or object to call on command failure. If no
                      callback is given, a "subprocess.CalledProcessError"
                      will be raised in case of command failure.
        - separate_stderr -- True to return command output as a 2-tuple
        - kwargs -- Additional arguments for the Popen constructor

    Returns:
        Number of failed commands

    """

    # stdout and stderr are specified by this code later, so they cannot be
    # overriden by user input
    for a in ["stdout", "stderr"]:
        if a in kwargs:
            raise ValueError("%s argument not allowed, " "it will be overridden." % a)

    # If no callback specified...
    if callback is None:
        # Raise CalledProcessError on command failure
        def callback(r, c, o):
            raise CalledProcessError(r, c, o)

    elif not callable(callback):
        raise ValueError("callback argument must be callable")

    # Manage stderr
    if separate_stderr:
        _stderr = subprocess.PIPE
        _get_output = lambda o, e: (o, e)
    else:
        _stderr = subprocess.STDOUT
        _get_output = lambda o, e: o

    # Iterate over commands
    error = 0
    for cmd in cmds:
        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=_stderr, shell=shell, **kwargs
        )

        output = _get_output(*process.communicate())
        retcode = process.poll()
        if retcode:
            error += 1
            if not callback(retcode, cmd, output):
                break
    return error
