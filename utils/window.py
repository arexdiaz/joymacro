from PyQt6.QtCore import QThread, pyqtSignal
from Xlib.protocol.event import ClientMessage
from Xlib.display import Display
from Xlib import X, Xatom, Xutil
from Xlib.error import XError
import logging

logger = logging.getLogger(__name__)

class Window:
    def __init__(self, win_id, display):
        self.id = win_id
        self.display = display
        self.window = display.create_resource_object("window", win_id)
        self.pid = self.get_pid()
        self.title = self.get_title()

    def get_pid(self):
        try:
            atom = self.display.intern_atom("_NET_WM_PID")
            prop = self.window.get_full_property(atom, Xatom.CARDINAL)
            return prop.value[0] if prop else None
        except XError:
            return None

    def get_title(self):
        try:
            atom = self.display.intern_atom("_NET_WM_NAME")
            prop = self.window.get_full_property(atom, self.display.intern_atom("UTF8_STRING"))
            if prop:
                return prop.value.decode("utf-8")
            atom = self.display.intern_atom("WM_NAME")
            prop = self.window.get_full_property(atom, Xatom.STRING)
            return prop.value.decode("latin1") if prop else "Unknown"
        except XError:
            return "Unknown"

    def get_net_wm_state(self):
        try:
            atom = self.display.intern_atom("_NET_WM_STATE")
            prop = self.window.get_full_property(atom, Xatom.ATOM)
            return [self.display.get_atom_name(a) for a in prop.value] if prop else []
        except XError:
            return []
    
    def close(self):
        try:
            wm_protocols = self.display.intern_atom("WM_PROTOCOLS")
            wm_delete = self.display.intern_atom("WM_DELETE_WINDOW")

            protocols = self.window.get_full_property(wm_protocols, Xatom.ATOM)
            if protocols and wm_delete in protocols.value:
                event = ClientMessage(
                    window=self.window,
                    client_type=wm_protocols,
                    data=(32, [wm_delete, X.CurrentTime, 0, 0, 0])
                )
                self.window.send_event(event, event_mask=X.NoEventMask)
                self.display.flush()
                print("Toggle close")
            else:
                logger.error("Window does not support WM_DELETE_WINDOW protocol")
        except XError as e:
            logger.error(f"Failed to close window {self.id}: {e}")

    def toggleFullscreen(self):
            try:
                wm_state = self.display.intern_atom("_NET_WM_STATE")
                fullscreen = self.display.intern_atom("_NET_WM_STATE_FULLSCREEN")

                event = ClientMessage(
                    window=self.window,
                    client_type=wm_state,
                    data=(32, [
                        2,
                        fullscreen,
                        0, 0, 0
                    ])
                )
                
                mask = X.SubstructureRedirectMask | X.SubstructureNotifyMask
                self.display.send_event(self.display.screen().root, event, mask)
                self.display.flush()
                
                logger.debug(f"Toggled fullscreen for window {self.id}")
            except XError as e:
                logger.error(f"Toggle failed: {e}")
        
    def toggleMaximize(self):
        try:
            wm_state = self.display.intern_atom("_NET_WM_STATE")
            max_vert = self.display.intern_atom("_NET_WM_STATE_MAXIMIZED_VERT")
            max_horz = self.display.intern_atom("_NET_WM_STATE_MAXIMIZED_HORZ")
            
            event = ClientMessage(
                window=self.window,
                client_type=wm_state,
                data=(32, [
                    2,
                    max_vert,
                    max_horz,
                    0, 0
                ])
            )
            
            mask = X.SubstructureRedirectMask | X.SubstructureNotifyMask
            self.display.send_event(self.display.screen().root, event, mask)
            self.display.flush()
            
            logger.info(f"Maximize for window {self.id}")
        except XError as e:
            logger.error(f"Toggle failed: {e}")

    def toggleMinimize(self):
        try:
            wm_change_state = self.display.intern_atom("WM_CHANGE_STATE")
            target_state = Xutil.IconicState if not self.is_minimized else Xutil.NormalState
            
            event = ClientMessage(
                window=self.window,
                client_type=wm_change_state,
                data=(32, [target_state, 0, 0, 0, 0])
            )
            
            mask = X.SubstructureRedirectMask | X.SubstructureNotifyMask
            self.display.send_event(self.display.screen().root, event, mask)
            self.display.flush()
            
            logger.debug(f"Minimize for window {self.id}")
        except XError as e:
            logger.error(f"Toggle failed: {e}")
            
    @property
    def get_fullscreen_type(self):
        try:
            # Check EWMH atoms first
            state = self.get_net_wm_state()
            override_redirect = self.window.get_attributes().override_redirect
            window_geometry = self.window.get_geometry()
            screen = self.display.screen()
            
            if (override_redirect and 
                "_NET_WM_FULLSCREEN" in state and 
                window_geometry.width == screen.width_in_pixels and 
                window_geometry.height == screen.height_in_pixels):
                return "Exclusive Fullscreen (override_redirect)"
            
            elif ("_NET_WM_STATE_FULLSCREEN" in state and 
                  not override_redirect and 
                  window_geometry.width == screen.width_in_pixels and 
                  window_geometry.height == screen.height_in_pixels):
                return "Borderless Fullscreen (windowed)"
            
            elif (window_geometry.width != screen.width_in_pixels or 
                  window_geometry.height != screen.height_in_pixels):
                return "Exclusive Fullscreen (resolution change)"
            
            else:
                return "Windowed"
            
        except XError:
            return "Unknown"

    @property
    def is_minimized(self):
        try:
            wm_state = self.display.intern_atom("WM_STATE")
            prop = self.window.get_full_property(wm_state, X.AnyPropertyType)
            return prop.value[0] == Xutil.IconicState if prop else False
        except XError:
            return False

    @property
    def is_maximized(self):
        state = self.get_net_wm_state()
        return "_NET_WM_STATE_MAXIMIZED_VERT" in state and "_NET_WM_STATE_MAXIMIZED_HORZ" in state

    @property
    def is_fullscreen(self):
        return "_NET_WM_STATE_FULLSCREEN" in self.get_net_wm_state()

    @property
    def is_active(self):
        try:
            atom = self.display.intern_atom("_NET_ACTIVE_WINDOW")
            prop = self.display.get_input_focus().focus
            return prop == self.window
        except XError:
            return False


class WindowMonitor(QThread):
    on_window_create = pyqtSignal(object)
    on_window_close = pyqtSignal(object)
    
    def __init__(self):
        super().__init__()

    def run(self):
        display = Display()
        root = display.screen().root
        net_client_list = display.intern_atom("_NET_CLIENT_LIST")

        root.change_attributes(event_mask=X.PropertyChangeMask)
        window_instances = {}  # {win_id: Window}

        client_list = root.get_full_property(net_client_list, Xatom.WINDOW)
        existing_windows = set(client_list.value) if client_list else set()

        for win_id in existing_windows:
            window = Window(win_id, display)
            window_instances[win_id] = window
            self.on_window_create.emit(window)
            logger.debug(f"Initialized: ID={win_id}, PID={window.pid}, Title='{window.title}'")

        try:
            while True:
                event = display.next_event()
                if event.type == X.PropertyNotify and event.atom == net_client_list:
                    client_list = root.get_full_property(net_client_list, Xatom.WINDOW)
                    new_windows = set(client_list.value) if client_list else set()

                    added = new_windows - window_instances.keys()
                    removed = window_instances.keys() - new_windows

                    for win_id in added:
                        window = Window(win_id, display)
                        window_instances[win_id] = window
                        self.on_window_create.emit(window)
                        logger.debug(f"Window created: ID={win_id}, PID={window.pid}, Title='{window.title}'")

                    for win_id in removed:
                        window = window_instances.pop(win_id)
                        self.on_window_close.emit(window)
                        logger.debug(f"Window closed: ID={win_id}, PID={window.pid}, Title='{window.title}'")

        except KeyboardInterrupt:
            display.close()