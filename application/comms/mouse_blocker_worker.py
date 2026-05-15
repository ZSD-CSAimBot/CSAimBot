"""Mouse input blocker worker — allows only left/right click and movement."""

import platform
import threading
import time

_OS = platform.system()


def _run_windows_blocker(stop_event):
    from pynput import mouse

    BLOCKED = {
        0x0207, 0x0208, 0x0209,  # middle button
        0x020A, 0x020E,           # scroll wheel
        0x020B, 0x020C, 0x020D,  # side buttons
    }

    listener_ref = [None]

    def win32_event_filter(msg, data):
        if msg in BLOCKED:
            listener_ref[0].suppress_event()
        return True

    listener = mouse.Listener(win32_event_filter=win32_event_filter)
    listener_ref[0] = listener
    listener.start()

    stop_event.wait()
    listener.stop()


def _run_linux_blocker(stop_event):
    import evdev

    devices = [evdev.InputDevice(p) for p in evdev.list_devices()]
    mouse_dev = None
    for dev in devices:
        caps = dev.capabilities()
        if "mouse" in dev.name.lower() or (
            evdev.ecodes.EV_REL in caps
            and evdev.ecodes.BTN_LEFT in caps.get(evdev.ecodes.EV_KEY, [])
        ):
            mouse_dev = dev
            break

    if not mouse_dev:
        return

    try:
        mouse_dev.grab()
    except (PermissionError, OSError):
        return

    virtual_mouse = evdev.UInput(
        {
            evdev.ecodes.EV_REL: [evdev.ecodes.REL_X, evdev.ecodes.REL_Y],
            evdev.ecodes.EV_KEY: [evdev.ecodes.BTN_LEFT, evdev.ecodes.BTN_RIGHT],
        },
        name="Robot_Filtered_Mouse",
    )

    mouse_dev.set_nonblocking(True)
    try:
        while not stop_event.is_set():
            try:
                for event in mouse_dev.read():
                    if event.type == evdev.ecodes.EV_REL and event.code in (
                        evdev.ecodes.REL_X,
                        evdev.ecodes.REL_Y,
                    ):
                        virtual_mouse.write_event(event)
                    elif event.type == evdev.ecodes.EV_KEY and event.code in (
                        evdev.ecodes.BTN_LEFT,
                        evdev.ecodes.BTN_RIGHT,
                    ):
                        virtual_mouse.write_event(event)
                    elif event.type == evdev.ecodes.EV_SYN:
                        virtual_mouse.write_event(event)
            except BlockingIOError:
                pass
            time.sleep(0.01)
    finally:
        mouse_dev.ungrab()
        virtual_mouse.close()


def mouse_blocker_worker(pipe_conn):
    running = True
    stop_event = None
    blocker_thread = None

    def _start():
        nonlocal stop_event, blocker_thread
        if blocker_thread and blocker_thread.is_alive():
            return
        stop_event = threading.Event()
        if _OS == "Windows":
            target = _run_windows_blocker
        elif _OS == "Linux":
            target = _run_linux_blocker
        else:
            return
        blocker_thread = threading.Thread(target=target, args=(stop_event,), daemon=True)
        blocker_thread.start()

    def _stop():
        nonlocal stop_event, blocker_thread
        if stop_event:
            stop_event.set()
        if blocker_thread:
            blocker_thread.join(timeout=2)
        stop_event = None
        blocker_thread = None

    while running:
        while pipe_conn.poll():
            msg = pipe_conn.recv()
            cmd = msg.get("cmd")
            if cmd == "START":
                _start()
            elif cmd == "STOP":
                _stop()
            elif cmd == "QUIT":
                running = False
                break
        time.sleep(0.05)

    _stop()
