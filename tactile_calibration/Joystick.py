import arcade
# Class for Jog Mode        
class Joystick(arcade.Window): 
    def __init__(self): 
        super().__init__(600, 600, title="Keyboard Inputs") 
        self.increment = 1

        # Print Keyboard Instructions
        print("")
        print("RIGHT ARROW: Moves in the +X direction")
        print("LEFT ARROW: Moves in the -X direction")
        print("UP ARROW: Moves in the +Y direction")
        print("DOWN ARROW: Moves in the -Y direction")
        print("W: Moves in the +Z direction")
        print("S: ARROW: Moves in the -Z direction")
        print("P: Sets jog increment to 0.1 mm")
        print("M: Sets jog increment to 1 mm")
        print("")
          
    # Creating function to check if button is pressed
    def on_key_press(self, symbol, send_gcode): 

        if symbol == arcade.key.UP: 
            # Move 1 mm in +Y direction
            send_gcode("G0 Y" + str(self.increment))
        elif symbol == arcade.key.DOWN: 
            # Move in -Y direction
            send_gcode("G0 Y-" + str(self.increment))
        elif symbol == arcade.key.RIGHT: 
            # Move in +X direction
            send_gcode("G0 X" + str(self.increment))
        elif symbol == arcade.key.LEFT: 
            # Move in -X direction
            send_gcode("G0 X-" + str(self.increment))
        elif symbol == arcade.key.W:
            # Move in +Z direction
            send_gcode("G0 Z" + str(self.increment))
        elif symbol == arcade.key.S:
            # Move in -Z direction
            send_gcode("G0 Z-" + str(self.increment))
        elif symbol == arcade.key.M:
            # Set movement to 1 mm increments
            self.increment = 1
        elif symbol == arcade.key.P:
            # Set movement to 0.1 mm increments
            self.increment = 0.1
