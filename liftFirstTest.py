import salabim as sim

# Ensure fully yieldless mode (default is True, but let's be explicit)
sim.yieldless(True)


class Scheduler(sim.Component):
    def setup(self):
        """ Create the components """
        # Create the Warehouse
        self.warehouse = Warehouse()

        # Add random items to the Warehouse (stock)
        self.warehouse.addItem(Item(name="Schroevendraaier"), tray_id=1)
        self.warehouse.addItem(Item(name="Plakband"), tray_id=1)

        # Make requests
        self.requests = []
        self.requests.append(Request("Schroevendraaier"))

        # Create an Operator and give it the requests
        self.operator = Operator(self.warehouse, self.requests)
    def process(self):
        # Activate the Operator
        self.operator.activate()





class Operator(sim.Component):
    def setup(self, warehouse, requests):
        self.warehouse = warehouse # The assigned warehouse
        self.requests = requests

    def process(self):
        # Process the requests
        for request in self.requests:
            item_name = request.item_name
            # Search in which tray the item is
            self.warehouse.locate_item(item_name)


class Elevator(sim.Component):
    def setup(self):
        self.current_level = 0
        self.target_level = 0
        self.capacity = 4
        self.items = []
        self.travel_speed = 2  # Time to move one floor
        self.present_time = 1

    def process(self):
        # Go to the target level, get or release the item(s)
        # Go to the target level
        travel_time = abs(self.target_level - self.current_level) * self.travel_speed
        self.hold(travel_time)


class Warehouse:
    def __init__(self, size):
        # Create the warehouse
        self.size = size # vertical size of the system = amount of levels

        # Create a tray for each level
        self.trays = [Tray(i) for i in range(size)]

        # Rest of the attributes
        self.elevator = Elevator()

    def addItem(self, item, tray_id):
        if 0 <= tray_id < self.size:  # Ensure tray_id is valid
            # Save the tray_id in the item for easy retrieval
            item.tray_ID = tray_id
            # Add the item
            self.trays[tray_id].add_item(item)
            print(f"Added '{item}' to Tray {tray_id}.")
        else:
            print(f"Invalid Tray ID {tray_id}! Must be between 0 and {self.size - 1}.")

    def remove_item(self, item, tray_id):
        if 0 <= tray_id < self.size:  # Ensure tray_id is valid
            removed_item = self.trays[tray_id].remove_item(item)
            if removed_item:
                print(f"Removed '{item}' from Tray {tray_id}.")
            return removed_item
        else:
            print(f"Invalid Tray ID {tray_id}! Must be between 0 and {self.size - 1}.")

    def locate_item(self, locate_item):
        """ Locate the tray that contains an item with the given name. """
        for tray in self.trays:  # Loop through all trays
            for current_item in tray.items:  # Loop through items in each tray
                if current_item.name == locate_item.name:  # Check if the name matches
                    return tray  # Return the tray that contains the item
        print(f"Item not present in the warehouse.")
        return None  # Return None if the item is not found

class Tray:
    def __init__(self, ID):
        self.ID = ID
        self.level = ID
        self.items = []
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


class Request:
    def __init__(self, item_name):
        self.item_name = item_name  # The item that needs to be retrieved


""" Main """
# Create the simulation environment
env = sim.Environment(trace=False)

# Create the Scheduler (this starts automatically when the environment starts running)
scheduler = Scheduler()

# Run the simulation for 30 time units
env.run(till=30)