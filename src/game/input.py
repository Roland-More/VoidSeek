class InputState:
    def __init__(self):
        self.forward: bool = False
        self.backward: bool = False
        self.left: bool = False
        self.right: bool = False
        self.interact: bool = False
        self.mouse_dx: float = 0.0
