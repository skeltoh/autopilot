import subprocess
import os
import sys
from autopilot import prefs
import atexit
from time import sleep
import threading
import shutil

PIGPIO = False
PIGPIO_DAEMON = None
PIGPIO_LOCK = threading.Lock()
try:
    if shutil.which('pigpiod') is not None:
        PIGPIO = True

except ImportError:
    pass

JACKD = False
# JACKD_MODULE = None # Whether jackd is a module in autopilot.external (True) or use system jackd (False)
JACKD_PROCESS = None
try:
    import jack
    JACKD = True
    # from autopilot.external import jack as autopilot_jack
    #
    # # set env variables
    # jackd_path = os.path.join(autopilot_jack.__path__._path[0])
    #
    # # specify location of libraries when starting jackd
    #
    #
    # if 'LD_LIBRARY_PATH' in os.environ.keys():
    #
    #     os.environ['LD_LIBRARY_PATH'] = ":".join([os.path.join(jackd_path, 'lib'),
    #                                               os.environ.get('LD_LIBRARY_PATH',"")])
    # else:
    #     os.environ['LD_LIBRARY_PATH'] = os.path.join(jackd_path, 'lib')git pu
    # # lib_string = "LD_LIBRARY_PATH=" + os.path.join(jackd_path, 'lib')
    #
    # # specify location of drivers when starting jackd
    # os.environ['JACK_DRIVER_DIR'] = os.path.join(jackd_path, 'lib', 'jack')
    # # driver_string = "JACK_DRIVER_DIR=" + os.path.join(jackd_path, 'lib', 'jack')
    #
    # JACKD = True
    # JACKD_MODULE = True

except (ImportError, OSError):
    pass
    # # try to import jack client, it will look for system jack by default
    # try:
    #     import jack
    #     JACKD = True
    #     JACKD_MODULE = False
    # except OSError:
    #     # no need to do anything, just setting module variables that test what the system is configured to do
    #     pass


def start_pigpiod():
    if not PIGPIO:
        raise ImportError('the pigpiod daemon was not found! use autopilot.setup.')

    with globals()['PIGPIO_LOCK']:
        if globals()['PIGPIO_DAEMON']:
            return globals()['PIGPIO_DAEMON']

        launch_pigpiod = shutil.which('pigpiod')
        if launch_pigpiod is None:
            raise RuntimeError('the pigpiod binary was not found!')

        if hasattr(prefs, 'PIGPIOARGS'):
            launch_pigpiod += ' ' + prefs.PIGPIOARGS

        if hasattr(prefs, 'PIGPIOMASK'):
            # if it's been converted to an integer, convert back to a string and zfill any leading zeros that were lost
            if isinstance(prefs.PIGPIOMASK, int):
                prefs.PIGPIOMASK = str(prefs.PIGPIOMASK).zfill(28)
            launch_pigpiod += ' -x ' + prefs.PIGPIOMASK

        proc = subprocess.Popen('sudo ' + launch_pigpiod, shell=True)
        globals()['PIGPIO_DAEMON'] = proc

        # kill process when session ends
        atexit.register(lambda pigpio_proc=proc: pigpio_proc.kill())

        # sleep to let it boot up
        sleep(1)

        return proc

def start_jackd():
    if not JACKD:
        raise ImportError('jackd was not found in autopilot.external or as a system install')

    # get specific launch string from prefs
    if hasattr(prefs, "JACKDSTRING"):
        jackd_string = prefs.JACKDSTRING.lstrip('jackd')

    else:
        jackd_string = ""

    # construct rest of launch string!
    # if JACKD_MODULE:
    #     jackd_path = os.path.join(autopilot_jack.__path__._path[0])
    #
    #     # now set as env variables...
    #     # specify location of libraries when starting jackd
    #     # lib_string = "LD_LIBRARY_PATH=" + os.path.join(jackd_path, 'lib')
    #     #
    #     # specify location of drivers when starting jackd
    #     # os.environ['JACK_DRIVER_DIR'] = os.path.join(jackd_path, 'lib', 'jack')
    #     # driver_string = "JACK_DRIVER_DIR=" + os.path.join(jackd_path, 'lib', 'jack')
    #
    #     jackd_bin = os.path.join(jackd_path, 'bin', 'jackd')
    #
    #     # combine all the pieces
    #     # launch_jackd = " ".join([lib_string, driver_string, jackd_bin, jackd_string])
    #
    # else:
    jackd_bin = 'jackd'

        # launch_jackd = " ".join([jackd_bin, jackd_string])

    launch_jackd = " ".join([jackd_bin, jackd_string])

    proc = subprocess.Popen(launch_jackd, shell=True)
    globals()['JACKD_PROCESS'] = proc

    # kill process when session ends
    atexit.register(lambda jackd_proc=proc: jackd_proc.kill())

    # sleep to let it boot
    sleep(1)

    return proc

