import subprocess
try:
    from pipes import quote # Python2 & Python3 <= 3.2
except ImportError:
    from shlex import quote # Python3 >= 3.3

from .stream import NonBlockingStreamReader

# Prevent to import subprocess only for common classes
CalledProcessError = subprocess.CalledProcessError


# Alternative subprocess methods ---------------------------------------

def check_output(args, stderr=subprocess.STDOUT, shell=True, **kwargs):
    """Run command with arguments and return its output as a byte string

    Overwrite some of the arguments to capture standard error in the result
    and use shell by default before calling subprocess.check_output.

    """
    return subprocess.check_output(args, stderr=stderr, shell=shell, **kwargs)


# Call with stream access ----------------------------------------------

def call_async_output(args, callback, **kwargs):
    """Run command and provide its output asynchronously

    Run command with arguments and wait for it to complete to return the
    returncode attribute. The callback must take one byte string argument
    and will be called each time the command produces some output.

    The stdout and stderr additional arguments for the Popen constructor
    are not allowed as they are used internally.

    Keyword arguments:
        - args -- String or sequence of program arguments
        - callback -- Method or object to call with output as argument
        - **kwargs -- Additional arguments for the Popen constructor

    Returns:
        Exit status of the command

    """
    for a in ['stdout', 'stderr']:
        if a in kwargs:
            raise ValueError('%s argument not allowed, '
                             'it will be overridden.' % a)
    if not callable(callback):
        raise ValueError('callback argument must be callable')

    # Run the command
    p = subprocess.Popen(args, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, **kwargs)

    # Wrap and get command output
    stream = NonBlockingStreamReader(p.stdout)
    while True:
        line = stream.readline(True, 0.1)
        if not line:
            # Check if process has terminated
            returncode = p.poll()
            if returncode is not None:
                break
        else:
            try:
                callback(line.rstrip())
            except:
                pass
    stream.close()

    return returncode


# Call multiple commands -----------------------------------------------

def check_commands(cmds, raise_on_error=False, callback=None,
                   separate_stderr=False, shell=True, **kwargs):
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
        - raise_on_error -- True to raise a CalledProcessError on error if
            no callback is provided
        - callback -- Method or object to call on command failure
        - separate_stderr -- True to return command output as a 2-tuple
        - **kwargs -- Additional arguments for the Popen constructor

    Returns:
        Number of failed commands

    """
    for a in ['stdout', 'stderr']:
        if a in kwargs:
            raise ValueError('%s argument not allowed, '
                             'it will be overridden.' % a)
    error = 0

    if callback is None:
        if raise_on_error:
            # Raise on command failure
            def callback(r, c, o):
                raise CalledProcessError(r, c, o)
        else:
            # Continue commands execution
            callback = lambda r,c,o: True
    elif not callable(callback):
        raise ValueError('callback argument must be callable')

    # Manage stderr
    if separate_stderr:
        _stderr = subprocess.PIPE
        _get_output = lambda o,e: (o,e)
    else:
        _stderr = subprocess.STDOUT
        _get_output = lambda o,e: o

    # Iterate over commands
    for cmd in cmds:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                   stderr=_stderr, shell=shell, **kwargs)
        output = _get_output(*process.communicate())
        retcode = process.poll()
        if retcode:
            error += 1
            if not callback(retcode, cmd, output):
                break
    return error
