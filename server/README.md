## Info
Code responsible for initial server communication, check and provide updates,
version resolutions and removement of deprecated versions. This code can be
used before main "OpenPype" package is imported, but can also be used within
the package.

Package probably should be added only to sys.path on launch and skip PYTHONPATH
because it would be unsafe to use it outside of OpenPype process. This
condition would give option to avoid Python 2 compatibility.
