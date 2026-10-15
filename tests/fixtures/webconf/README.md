The complete `zynthian_webconf.py.txt` fixture comes from Zynthian Webconf Oram
commit `0e2c2556dd4db2aaddd42c8a6de8db9bd225d477`:
https://github.com/zynthian/zynthian-webconf/blob/0e2c2556dd4db2aaddd42c8a6de8db9bd225d477/zynthian_webconf.py

Its upstream copyright/license header is preserved. Installer tests compile the
hooked source and verify exact ownership/rollback; they do not pretend to start
all hardware-dependent Webconf handlers. HTTP/API/WS fixtures use a real Tornado
Application and the actual native MBMF engine/editor workers. Avahi method calls
and interface changes are explicitly simulated; physical publication is untested.
