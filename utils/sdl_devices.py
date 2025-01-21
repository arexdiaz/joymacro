import warnings
warnings.filterwarnings("ignore", message="Using SDL2 binaries from pysdl2-dll 2.30.2")
import sdl2
import sdl2.ext
import logging

class SDLDevices:
    def __init__(self):
        sdl2.ext.init()
        sdl2.SDL_Init(sdl2.SDL_INIT_JOYSTICK)
        self.joysticks = []
        self.num_joysticks = sdl2.SDL_NumJoysticks()
        self.held_buttons = set()
        self.held_axis = set()
        self.held_hat = 0
        self.get_joys()


    def get_joys(self):
        for i in range(self.num_joysticks):
            joystick = sdl2.SDL_JoystickOpen(i)
            if joystick:
                self.joysticks.append({"name": sdl2.SDL_JoystickName(joystick).decode("utf-8"), "device": joystick})

    def joy_lstnr(self, event):
        joy_id = event.jbutton.which
        if event.type == sdl2.SDL_JOYBUTTONDOWN:
            button = event.jbutton.button
            self.held_buttons.add(button)
        elif event.type == sdl2.SDL_JOYBUTTONUP:
            self.held_buttons.remove(event.jbutton.button)
        elif event.type == sdl2.SDL_JOYAXISMOTION:
            axis = event.jaxis.axis
            value = event.jaxis.value
            if axis in (4, 5):
                if value == 32768:
                    self.held_axis.add(axis)
                else:
                    self.held_axis.remove(axis)
        elif event.type == sdl2.SDL_JOYHATMOTION:
            hat = event.jhat.value
            self.held_hat = hat
        elif event.type == sdl2.SDL_JOYDEVICEADDED:
            logging.debug("Device added")
            self.get_joys()
        elif event.type == sdl2.SDL_JOYDEVICEREMOVED:
            logging.debug("Device removed")
            self.get_joys()

        return [self.held_buttons, self.held_axis, self.held_hat]
