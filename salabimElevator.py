import math
import salabim as sim
import yaml
from types import SimpleNamespace


''' =============== Global parameters and variables =============== '''
# Ensure fully yieldless mode (default is True, but let's be explicit)
sim.yieldless(False)

# Load configuration file as YAML file
def load_config(filepath):
    with open(filepath, "r") as f:
        data = yaml.safe_load(f)
    return SimpleNamespace(**data)

# Adjustable parameters. Make a new YAML file if you want different configurations
# All parameters are now in yaml files
# Call with "config.<PARAMETER_NAME>"
config = load_config("Configurations/1-machine_1-lift.yaml")

event_log = []
unfulfilled_requests = []


''' ====================== Classes ====================== '''
class Operator(sim.Component):
    def setup(self):
        # picking time
        self.pick_time = [10, 12, 14, 11]

    def process(self):
        # Process the requests. Each request is a list of items
        for request in requests:
            print("\n\n============================= NEW ORDER =============================")
            for item_name in request.item_names:
                print(f"-------- {item_name.upper()} -------")
                # Retreive request information
                print(f"Processing the request: {item_name}\n")

                # Search in which tray the item is
                item_tray = warehouse.locate_item(item_name)
                if (item_tray == None):
                    unfulfilled_requests.append(request)
                    # Volledige request mag niet gedaan worden. Op voorhand check of volledige order op stock?
                    raise Exception("Nog niet klaar, verder werken")
                print(f"The item \"{item_name}\" is in tray {item_tray}")

                # Operator starts the elevator
                print(f"Operator called the elevator to retrieve item at time {env.now():.2f}")

                # Let the elevator get the item.
                print(f"Task: Elevator will get {item_tray} with item: {item_name}")
                elevator.setTarget(item_tray, item_name)
                elevator.activate()

                # wait until the elevator is back
                elevator_done.reset()  # Reset the sim.State "elevator_done".
                self.wait(elevator_done)  # Wait until elevator_done.set is called (in elevator process)
                print(f"The tray with the item is in front of the operator at time {env.now():.2f}")

                # Handle the item - Picking time
                yield self.hold(self.pick_time[0])
                print(f"The operator finished picking the item at time {env.now():.2f}")

                # Press a button to return the tray. Elevator is activated again
                print(f"The operator pressed the elevator button at time {env.now():.2f}")
                print(f"The lift is now returning the item")
                elevator.switchTask()
                elevator.activate()
                # wait until the elevator is back
                elevator_done.reset()
                self.wait(elevator_done)

                # The operator can handle the next request (the elevator might still be active returning)
                elevator.switchTask()  # switches back to retrieveTray



class Elevator(sim.Component):
    def setup(self):
        self.current_level = 0
        self.task = "retrieveTray"  # retrieveTray: bring tray to operator | returnTray: return tray to original place

        # different speeds
        # self.travel_speed = 2   # Time to move one floor
        # self.travel_acceleration = 1
        # self.max_travel_speed = 2
        self.retrieve_time = config.ELEVATOR_RETRIEVE_TIME  # Time to retrieve the tray from the warehouse onto the elevator
        self.return_time = config.ELEVATOR_RETURN_TIME      # Time to return the tray back into the warehouse
        self.present_time = config.ELEVATOR_RETURN_TIME     # Time to get the tray from the elevator to the operator

        # Target information
        self.target_tray_id = None
        self.target_level = None
        self.target_tray_number = None  # which one of the 2 trays it is on a certain level

        # Only start when operator calls for it
        self.passivate()
        self.item = None

        #############################
        #Code Visualisatie
        self.y_position = BASE_Y + self.current_level * LEVEL_HEIGHT
        self.pause_at_level_time = 2.0  # Tijd om even te pauzeren bij aankomst

        #############################


    def setTarget(self, target_tray, item_name):
        self.target_tray_id = target_tray.ID
        self.target_level = target_tray.ID // 2
        self.target_tray_number = target_tray.ID % 2  # is '0' or '1'
        self.item = item_name

    def switchTask(self):
        if self.task == "retrieveTray":
            self.task = "returnTray"
        elif self.task == "returnTray":
            self.task = "retrieveTray"
        else:
            print(f"\n\nERROR: Elevator task is unusual!\n\n")

    def retrieveTray(self):
        # Go to the target level, get or release the item(s)
        # Go to the target level
        start_loc = self.current_level
        start_time = env.now()

        print("\nElevator travel event:")
        print(f"Elevator going from level {self.current_level} to level {self.target_level} at time {env.now():.2f}")
        yield from self.move_to_level(self.target_level)
        print(f"Elevator arrived at level {self.target_level} at time {env.now()} and is ready to retrieve the tray\n")

        # Retrieve the tray
        yield self.hold(self.retrieve_time)
        print(f"Tray is loaded on elevator at time {env.now():.2f}")

        # Go to the operator
        print("\nElevator travel event:")
        print(f"Elevator going from level {self.current_level} to level {OPERATOR_LEVEL} at time {env.now():.2f}")

        # Nieuwe Code Visualisatie
        yield from self.move_to_level(OPERATOR_LEVEL)

        print(f"Elevator arrived at level {OPERATOR_LEVEL} at time {env.now():.2f}\n")

        # Present the tray to the operator
        yield self.hold(self.present_time)
        print(f"The tray is ready for the operator at time {env.now():.2f}")

        # The operator will handle the item and press a button to call the elevator to return the tray
        # The button is calling the function switchTask and restarts the process


    def returnTray(self):
        # The target tray variable should still be correct (it isn't changed in the meantime)
        start_time = env.now()
        start_loc = self.current_level

        # Put the tray back on the elevator
        yield self.hold(self.retrieve_time)
        print(f"\nTray is loaded on elevator at time {env.now():.2f}")

        # Go to the target level
        print("\nElevator travel event:")
        print(f"Elevator going from level {self.current_level} to level {self.target_level} at time {env.now():.2f}")

        # Nieuwe Code Visualisatie
        yield from self.move_to_level(self.target_level)

        print(f"Elevator arrived at level {self.target_level} at time {env.now():.2f} and is ready to return the tray\n")

        # Return the tray into the warehouse
        yield self.hold(self.return_time)
        print(f"Tray is returned to the warehouse at time {env.now():.2f}")

        # The lift can stay at its current location since there is only 1 elevator


    def process(self):
        if (self.task == "retrieveTray"):
            yield from self.retrieveTray()
        else:
            yield from self.returnTray()

        # Let the operator know the elevator is finished
        elevator_done.set()

    #############################
    #Visualisatie Code
    #Tray smooth laten bewegen
    def move_to_level(self, target_level):
        steps = 100
        start_level = self.current_level
        start_y = BASE_Y + start_level * LEVEL_HEIGHT
        end_y = BASE_Y + target_level * LEVEL_HEIGHT
        total_time = calculate_travel_time(start_level, target_level)
        time_per_step = total_time / steps

        for i in range(1, steps + 1):
            frac = i / steps
            self.y_position = start_y + frac * (end_y - start_y)
            yield self.hold(time_per_step)

        self.y_position = end_y  # zorg dat eindpositie exact klopt
        yield self.hold(self.pause_at_level_time)  # korte pauze zichtbaar
        self.current_level = target_level

    #############################

class Warehouse:
    def __init__(self, height):
        # Create the warehouse
        self.height = height  # vertical height of the system = amount of levels

        # Create the trays. Each level has 2 trays. So height*2 trays
        self.trays = [Tray(i) for i in range(height * 2)]

    def addItem(self, item, tray_id):

        # Ensure tray_id is valid
        if 0 <= tray_id < self.height * 2:  # Ensure tray_id is valid
            # Save the tray_id in the item for easy retrieval
            item.tray_ID = tray_id
            # Add the item
            self.trays[tray_id].add_item(item)
            print(f"Added '{item}' to Tray {tray_id}.")
        else:
            print(f"Invalid Tray ID {tray_id}! Must be between 0 and {self.height - 1}.")

    def remove_item(self, item, tray_id):
        if 0 <= tray_id < self.height:  # Ensure tray_id is valid
            removed_item = self.trays[tray_id].remove_item(item)
            if removed_item:
                print(f"Removed '{item}' from Tray {tray_id}.")
            return removed_item
        else:
            print(f"Invalid Tray ID {tray_id}! Must be between 0 and {self.height - 1}.")

    def locate_item(self, item_name):
        """ Locate the tray that contains an item with the given name. """
        for tray in self.trays:  # Loop through all trays
            for current_item in tray.items:  # Loop through items in each tray
                if current_item.name == item_name:  # Check if the name matches
                    return tray  # Return the tray that contains the item
        print(f"Item not present in the warehouse.")
        return None  # Return None if the item is not found

class Tray:
    def __init__(self, ID):
        self.ID = ID
        # There are 2 trays for each level
        self.level = ID // 2
        self.trayNumber = ID % 2
        self.items = []

    def __str__(self):
        return f"Tray(ID={self.ID})"

    def add_item(self, item):
        self.items.append(item)

    def remove_item(self, item):
        if item in self.items:
            self.items.remove(item)
        else:
            print(f"Item '{item}' not found in Tray {self.ID}!")

class Item:
    def __init__(self, name):
        self.name = name
        self.tray_ID = None

    def __str__(self):
        return f"Item(name={self.name})"

class Request:
    def __init__(self, item_names):
        self.item_names = item_names  # The items that needs to be retrieved

class EventElevator:
    def __init__(self, item: str, start_locatie: int, start_tijd: float, eind_locatie: int, eind_tijd: float):
        self.item = item
        self.start_locatie = start_locatie
        self.start_tijd = start_tijd
        self.eind_locatie = eind_locatie
        self.eind_tijd = eind_tijd

    def __repr__(self):
        return (f"EventElevator(item={self.item}, start_locatie={self.start_locatie}, "
                f"start_tijd={self.start_tijd}, eind_locatie={self.eind_locatie}, eind_tijd={self.eind_tijd})")

''' ====================== Help functions ====================== '''
def nth_root(x, base):
    """
    Calculates the n'th root of a value (square-, qube-, ... root)
    """
    if base == 0:
        raise ValueError("Cannot take the 0th root.")
    if x < 0 and base % 2 == 0:
        raise ValueError("Cannot take even root of a negative number in real numbers.")
    return x ** (1 / base)

def calculate_travel_time(start, end):
    """
    Time to travel a certain distance, according to 4 different trajectory shapes:
    - Type 1: triangular,   continuous
    - Type 2: triangular,   non-continuous
    - Type 3: trapezoidal,  continuous
    - Type 4: trapezoidal,  non-continuous

    Trapezoidal means there is a period where a maximum acceleration is reached (triangular if it didn't)
    non-continuous means there is a period where an acceleration of 0 is maintained (maximum velocity)

    :parameters:
        - start: Begin position Elevator    (Integer)
        - end: End position of Elevator     (Integer)

    :variables:
        - s_tot: distance you want to travel    (meters)
        - j_max: maximum jerk                   (m/s^3)
        - a_max: maximum acceleration           (m/s^2)
        - t_v: time from v=0 to the end of v=v_max
        - t_a: time from a=0 to the end of a=a_max
        - t_j: Time for a jerk puls at j_max
    """
    # Target
    s_tot = abs(end - start)

    # Constants
    v_max = 0.6     # m/s
    a_max = 1.0     # m/s^2
    j_max = 20      # m/s^3

    ### Determine the type of trajectory shape. There are 3 values used for the conditions: ###
    # Value 1
    v_a = a_max**2 / j_max
    # Value 2
    s_a = (2 * a_max**3) / j_max ** 2
    # Value 3
    if (v_max <= v_a):
        s_v = v_max * 2 * math.sqrt(v_max / j_max)
    else:
        s_v = v_max * ((v_max / a_max) + (a_max / j_max))

    # Determine the shape based on the conditions
    if (s_a > s_tot and s_v > s_tot):
        shape = 1
    elif (v_a > v_max and s_v < s_tot):
        shape = 2
    elif (v_a < v_max and s_a < s_tot):
        shape = 3
    elif (v_a < v_max and s_a < s_tot and s_v < s_tot):
        shape = 4
    else:
        raise ValueError("The trajectory shape could not be determined")

    ### Characteristic time intervals ###
    # initialize time intervals
    t_j = 0
    t_a = 0
    t_v = 0

    # Calculate the time intervals
    if shape == 1:
        # time intervals
        t_j = nth_root(s_tot / (2 * j_max), base=3)
        t_a = 0
        t_v = 0
    elif shape == 2:
        t_j = nth_root(v_max / j_max, base=2)
        t_a = 0
        t_v = (s_tot / v_max) - 2 * nth_root(v_max / j_max, base=2)
    elif shape == 3:
        t_j = a_max / j_max
        t_a = 0.5 * (
            nth_root(((4 * s_tot * j_max ** 2 + a_max ** 3) / (a_max * j_max ** 2)) - (3 * a_max / j_max), base=2))
        t_v = 0
    elif shape == 4:
        t_j = a_max / j_max
        t_a = v_max / a_max - a_max / j_max
        t_v = s_tot / v_max - v_max / a_max - a_max / j_max
    else:
        print("X | There was no shape defined!")

    # The total time it took to travel s_tot
    return t_j + t_a + t_v


''' ====================== MAIN ====================== '''
# Create the simulation environment
env = sim.Environment(trace=False)

# Create a state to help with synchronization
elevator_done = sim.State('elevator_done')

# Create the components
warehouse = Warehouse(config.WAREHOUSE_HEIGHT)

# Add random items to the Warehouse (stock)
warehouse.addItem(Item(name="Schroevendraaier"), tray_id=3)
warehouse.addItem(Item(name="Plakband"), tray_id=3)
warehouse.addItem(Item(name="Schoen"), tray_id=2)
warehouse.addItem(Item(name="test"), tray_id=5)
warehouse.addItem(Item(name="Schoen"), tray_id=2)
# Make requests
requests = []
requests.append(Request(item_names=["Schroevendraaier", "Schroevendraaier", "Plakband"]))
requests.append(Request(item_names=["Schoen"]))
requests.append(Request(item_names=["test"]))
requests.append(Request(item_names=["test"]))
requests.append(Request(item_names=["test"]))
requests.append(Request(item_names=["test"]))
requests.append(Request(item_names=["test"]))
requests.append(Request(item_names=["test"]))
requests.append(Request(item_names=["test"]))
requests.append(Request(item_names=["test"]))
requests.append(Request(item_names=["test"]))
requests.append(Request(item_names=["test"]))
requests.append(Request(item_names=["test"]))
requests.append(Request(item_names=["test"]))
requests.append(Request(item_names=["test"]))
requests.append(Request(item_names=["test"]))


# Create an Operator and give it the necessary objects
# The operator is the only Component that executes its process method from the start
operator = Operator()
elevator = Elevator()

########################################################################################
#Start Visualisatie code
env.animate(True)



# Visualiseer de trays
for level in range(WAREHOUSE_HEIGHT):
    tray_y = BASE_Y + level * LEVEL_HEIGHT

    sim.AnimateRectangle(
        (-TRAY_WIDTH // 2, -TRAY_HEIGHT // 2, TRAY_WIDTH // 2, TRAY_HEIGHT // 2),
        x=TRAY_X_LEFT,
        y=tray_y,
        fillcolor='gray',
        linecolor='black',  # ➜ zwarte rand
        linewidth=1,  # ➜ dunne lijn
        text=f"Level {level}",
        text_anchor="center",
        fontsize=14  # ➜ grotere tekst
    )

    sim.AnimateRectangle(
        (-TRAY_WIDTH // 2, -TRAY_HEIGHT // 2, TRAY_WIDTH // 2, TRAY_HEIGHT // 2),
        x=TRAY_X_RIGHT,
        y=tray_y,
        fillcolor='gray',
        linecolor='black',  # ➜ zwarte rand
        linewidth=1,  # ➜ dunne lijn
        text=f"Level {level}",
        text_anchor="center",
        fontsize=14  # ➜ grotere tekst
    )
    sim.AnimateRectangle(
        (-TRAY_WIDTH // 2, -TRAY_HEIGHT // 2, TRAY_WIDTH // 2, TRAY_HEIGHT // 2),
        x=LIFT_X_POSITION,
        y=lambda: elevator.y_position,     # ➜ volgt real-time de positie van de lift
        fillcolor='blue',
        linecolor='black',
        text=lambda: elevator.item if elevator.item else "Lift",
        text_anchor="center",
        fontsize=14
    )
env.run(30)

for event in event_log:
    print(event)



