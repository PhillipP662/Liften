import salabim as sim


# Ensure fully yieldless mode (default is True, but let's be explicit)
sim.yieldless(True)

# Adjustable parameters
WAREHOUSE_HEIGHT = 4        # with 2 trays per level -> WAREHOUSE_HEIGHT*2 total trays
OPERATOR_LEVEL = 0          # At which level the operator is working
AMOUNT_OF_ELEVATORS = 1     # DON'T CHANGE YET! Not yet implemented for 1+ elevators


class Operator(sim.Component):
    def setup(self):
        # speeds/times
        self.retrieve_item_time = 1
        self.handle_item_time = 1
        self.press_button_time = 1

    def process(self):
        # Process the requests. Each request is a list of items
        for request in requests:
            print("\n\n============================= NEW ORDER =============================")
            for item_name in request.item_names:
                print(f"-------  {item_name.upper()} -------")
                # Retreive request information
                print(f"Processing the request: {item_name}\n")

                # Search in which tray the item is
                item_tray = warehouse.locate_item(item_name)
                if(item_tray==None):
                    unfulfilled_requests.append(request)
                    # Volledige request mag niet gedaan worden. Op voorhand check of volledige order op stock?
                    raise Exception("Nog niet klaar, verder werken")
                print(f"The item \"{item_name}\" is in tray {item_tray}")

                # Operator starts the elevator
                print(f"Operator called the elevator to retrieve item at time {env.now()}")

                # Let the elevator get the item.
                print(f"Tray: {item_tray} with item: {item_name}")
                elevator.setTarget(item_tray)
                elevator.activate()

                # wait until the elevator is back
                elevator_done.reset()       # Reset the sim.State "elevator_done".
                self.wait(elevator_done)    # Wait until elevator_done.set is called (in elevator process)
                print(f"The tray with the item is in front of the operator at time {env.now()}")

                # Handle the item
                self.hold(self.retrieve_item_time)
                print(f"The operator finished retrieving the item at time {env.now()}")
                self.hold(self.handle_item_time)
                print(f"The operator finished handling the item at time {env.now()}")

                # Press a button to return the tray. Elevator is activated again
                self.hold(self.press_button_time)
                print(f"The operator finished pressing the elevator button at time {env.now()}")
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
        self.task = "retrieveTray"      # retrieveTray: bring tray to operator | returnTray: return tray to original place

        # different speeds
        self.travel_speed = 2   # Time to move one floor
        self.retrieve_time = 1  # Time to retrieve the tray from the warehouse on the elevator
        self.return_time = 1    # Time to return the tray back into the warehouse
        self.present_time = 1   # Time to get the tray from the elevator to the operator

        # Target information
        self.target_tray_id = None
        self.target_level = None
        self.target_tray_number = None  # which one of the 2 trays it is on a certain level

        # Only start when operator calls for it
        self.passivate()

    def setTarget(self, target_tray):
        self.target_tray_id = target_tray.ID
        self.target_level = target_tray.ID // 2
        self.target_tray_number = target_tray.ID % 2    # is '0' or '1'

    def switchTask(self):
        if(self.task == "retrieveTray"):
            self.task = "returnTray"
        elif(self.task == "returnTray"):
            self.task = "retrieveTray"
        else:
            print(f"\n\nERROR: Elevator task is unusual!\n\n")

    def retrieveTray(self):
        # Go to the target level, get or release the item(s)
        # Go to the target level
        travel_time = abs(self.target_level - self.current_level) * self.travel_speed
        print(f"\nElevator going from level {self.current_level} to level {self.target_level} at time {env.now()}")
        self.hold(travel_time)
        self.current_level = self.target_level
        print(f"Elevator arrived at level {self.target_level} at time {env.now()} and is ready to retrieve the tray")

        # Retrieve the tray
        self.hold(self.retrieve_time)
        print(f"Tray is loaded on elevator at time {env.now()}")

        # Go to the operator
        travel_time = abs(OPERATOR_LEVEL - self.current_level) * self.travel_speed
        print(f"Elevator going from level {self.current_level} to level {OPERATOR_LEVEL} at time {env.now()}")
        self.hold(travel_time)
        self.current_level = OPERATOR_LEVEL
        print(f"Elevator arrived at level {OPERATOR_LEVEL} at time {env.now()}")

        # Present the tray to the operator
        self.hold(self.present_time)
        print(f"The tray is ready for the operator at time {env.now()}")

        # The operator will handle the item and press a button to call the elevator to return the tray
        # The button is calling the function switchTask and restarts the process

    def returnTray(self):
        # The target tray information should still be correct (it isn't changed in the meantime)
        # Put the tray back on the elevator
        self.hold(self.retrieve_time)
        print(f"\nTray is loaded on elevator at time {env.now()}")

        # Go to the target level
        travel_time = abs(self.target_level - self.current_level) * self.travel_speed
        print(f"Elevator going from level {self.current_level} to level {self.target_level} at time {env.now()}")
        self.hold(travel_time)
        self.current_level = self.target_level
        print(f"Elevator arrived at level {self.target_level} at time {env.now()} and is ready to return the tray")

        # Return the tray into the warehouse
        self.hold(self.return_time)
        print(f"Tray is returned to the warehouse at time {env.now()}")

        # The lift can stay at its current location since there is only 1 elevator

    def process(self):
        if(self.task == "retrieveTray"):
            self.retrieveTray()
        else:
            self.returnTray()

        # Let the operator know the elevator is finished
        elevator_done.set()

class Warehouse:
    def __init__(self, height):
        # Create the warehouse
        self.height = height # vertical height of the system = amount of levels

        # Create the trays. Each level has 2 trays. So height*2 trays
        self.trays = [Tray(i) for i in range(height*2)]

    def addItem(self, item, tray_id):
        if 0 <= tray_id < self.height*2:  # Ensure tray_id is valid
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


""" Main """
# Create the simulation environment
env = sim.Environment(trace=False)

# Create a state to help with synchronization
elevator_done = sim.State('elevator_done')

# Create the components
warehouse = Warehouse(WAREHOUSE_HEIGHT)

# Add random items to the Warehouse (stock)
warehouse.addItem(Item(name="Schroevendraaier"), tray_id=3)
warehouse.addItem(Item(name="Plakband"), tray_id=3)
warehouse.addItem(Item(name="Boor"), tray_id=5)
warehouse.addItem(Item(name="Tang"), tray_id=3)

# Make requests
requests = []
requests.append(Request(item_names=["Schroevendraaier", "Plakband"]))
requests.append(Request(item_names=["Boor", "Plakband", "Tang"]))

# List for unfulfilled requests (items not in stock)
unfulfilled_requests = []

# Create the Elevator
elevator = Elevator()

# Create an Operator. It has access to the other objects in the Main (Elevator, requests, ...)
operator = Operator()

# Run the simulation for 30 time units
env.run(till=30)
