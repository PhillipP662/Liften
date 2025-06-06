import json
import math
import os
from collections import Counter

import numpy as np
import salabim as sim
import yaml
from types import SimpleNamespace
from salabim import SimulationStopped

# To get the result of other python scripts
from Dataverwerking_code.for_main.VerdelingBestellingen import get_inventory_and_orders
from Dataverwerking_code.for_main.Tray_filling import get_tray_filling_from_data
from Dataverwerking_code.for_main.Picktijden import generate_picktime_samples

''' =============== Global parameters and variables =============== '''
USE_PRINT = False

def debug_print(*args, **kwargs):
    # use this instead of "print". it automatically checks if USE_PRINT is set or not
    if USE_PRINT:
        print(*args, **kwargs)

# Ensure fully yieldless mode (default is True, but let's be explicit)
sim.yieldless(False)

# Load configuration file which is a YAML file
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
    def setup(self, amount_of_items):
        # picking time
        self.pick_time = generate_picktime_samples(n=amount_of_items)
        self.pick_time_index = 0

    def process(self):
        if config.AMOUNT_OF_ELEVATORS == 1:
            yield from self.one_elevator()
        elif config.AMOUNT_OF_ELEVATORS == 2:
            yield from self.two_elevators()
        else:
            raise Exception("\n\nThere is no algorithm for more than 2 elevators\n\n")

        debug_print(f"\n\nOperator finished at time: {env.now()}")
        yield

    def one_elevator(self):
        # There are different preprocess strategies
        # 1: Orders stay the way they came in, items in an order are switched to put them in an optimal order
        # 2: Same as 1, but orders are sorted to put orders using the same tray together    -- ToDo
        if config.PRE_PROCESSING_STRATEGY == 2:
            # preprocess the requests list so that orders using the same items follow each other.
            # And since there are multiple items on a tray, all items on that tray can follow on each other as well.

            None  # Placeholder

        # Process the requests. Each request is a list of items
        for request_index, request in enumerate(requests):
            debug_print("\n\n============================= NEW ORDER =============================")
            # initialize global variables
            env.order_count += 1

            # If future items can already be taken from a retrieved tray, it can be taken directly instead of sending
            # the tray back, just to call the same tray again.
            # processed_indices is used to not process the already processed items again when continuing in the for loop
            processed_indices = set()

            for i in range(len(request.item_names)):
                if i in processed_indices:
                    continue  # already handled this index

                item_name = request.item_names[i]
                # initialize global variables
                env.request_start = env.now()
                env.item_picking_times = []

                debug_print(f"-------- {item_name.upper()} -------")
                # Retreive request information
                debug_print(f"Processing the request: {item_name}\n")

                # Search in which tray the item is
                item_tray = warehouse.locate_item(item_name)
                if (item_tray == None):
                    unfulfilled_requests.append(request)
                    # Volledige request mag niet gedaan worden. Op voorhand check of volledige order op stock?
                    raise Exception("Nog niet klaar, verder werken")
                debug_print(f"The item \"{item_name}\" is in tray {item_tray}")

                # Operator starts the elevator
                debug_print(f"Operator called the elevator to retrieve item at time {env.now():.2f}")

                # Let the elevator get the item.
                debug_print(f"Task: Elevator will get {item_tray} with item: {item_name}")
                elevator.setTarget(item_tray, item_name)
                elevator.activate()

                # wait until the elevator is back
                elevator_done.reset()  # Reset the sim.State "elevator_done".
                yield self.wait(elevator_done)  # Wait until elevator_done.set is called (in elevator process)
                debug_print(f"The tray with the item is in front of the operator at time {env.now():.2f}")

                # Handle the item - Picking time
                pick_time = self.pick_time[self.pick_time_index]  # placeholder; change with value from model
                self.pick_time_index += 1
                yield self.hold(pick_time)
                debug_print(f"Operator picked '{item_name}' from tray {item_tray.ID}")
                debug_print(f"The operator finished picking the item at time {env.now():.2f}")
                # The item is now gone from the tray
                warehouse.remove_item(item_name=item_name, tray_id=item_tray.ID)
                processed_indices.add(i)    # don't take it again

                # Update the global parameters and add to the jsonl files
                env.total_picking_time += pick_time
                env.picking_count += 1
                env.item_picking_times.append([item_name, pick_time])
                log_time(item_name, request_index, pick_time, log_type="picking")

                # if there are other items in the request already in the tray, pick them first,
                # instead of calling the same tray again.
                # item_counts is a list with each item name and how often it occurs in the current tray
                item_counts = Counter(item.name for item in item_tray.items)

                # scan through remaining items in the request
                for j in range(i + 1, len(request.item_names)):
                    # Skip already processed items
                    if j in processed_indices:
                        continue

                    future_name = request.item_names[j]

                    # If it's available in the tray, pick it
                    if item_counts.get(future_name, 0) > 0:  # (..., 0) with 0 as default value (ok for counting)
                        future_pick_time = self.pick_time[self.pick_time_index]
                        self.pick_time_index += 1
                        yield self.hold(future_pick_time)
                        warehouse.remove_item(item_name=future_name, tray_id=item_tray.ID)
                        item_counts[future_name] -= 1  # Decrease availability
                        processed_indices.add(j)  # Don't pick it again
                        debug_print(
                            f"Finished picking '{future_name}' from tray {item_tray.ID} in advance at time {env.now():.2f}")

                        # Update the global parameters and add to the jsonl file
                        env.total_picking_time += future_pick_time
                        env.picking_count += 1
                        env.item_picking_times.append([future_name, future_pick_time])
                        log_time(future_name, request_index, future_pick_time, log_type="picking")

                # Press a button to return the tray. Elevator is activated again
                debug_print(f"The operator pressed the elevator button at time {env.now():.2f}")
                debug_print(f"The elevator will now return the tray to the warehouse")
                elevator.switchTask()
                elevator.activate()
                # wait until the elevator is back
                elevator_done.reset()
                yield self.wait(elevator_done)

                # The operator can handle the next request
                elevator.switchTask()  # switches back to retrieveTray

                # Global throughput logic
                env.request_stop = env.now()
                elapsed_time = env.request_stop - env.request_start

                # update the item time variables (picking times were already updated)
                env.total_handling_time += elapsed_time
                env.item_count += len(env.item_picking_times)

                # add times to the jsonl file
                # Calculate how long each item took to process
                # When items were handled in a batch, split the shared time
                split_time = elapsed_time / len(env.item_picking_times)
                for element in env.item_picking_times:
                    log_time(item_code=element[0], request_index=request_index, time_value=element[1]+split_time, log_type="handling")


    def two_elevators(self):
        # Using 2 elevators, so the operator should look ahead at new trays to occupy the second elevator.
        # The elevators work as a pair, they don't work independently because of space restrictions,
        # meaning they can't go through each other
        # Let's call the bottom and top elevator lift0 and lift1 respectively
        # Different situations:
        # - Order with multiple items (and trays): use both elevators for the 1 order
        # - Order has 1 item: each elevator handles an order (lift0 takes the lowest tray and lift1 the highest)

        # Process the requests/orders
        # flatten the requests list to get a list of items (of all orders), but keep request index as metadata,
        # since the next order can't start if the current is not finished (or about to finish)

        # Preprocessing =================================================================================
        flattened_items = []

        for request_index, request in enumerate(requests):
            for item_index, item_name in enumerate(request.item_names):
                is_last = (item_index == len(request.item_names) - 1)
                flattened_items.append({
                    "item_name": item_name,
                    "request_index": request_index,
                    "is_last_in_request": is_last,  # if it is the last item of a request
                    "is_processed": False           # change to True when processed, so it doesn't happen twice
                })

        i = 0
        blacklist = []
        while i < len(flattened_items):
            item = flattened_items[i]

            if item.get("processed"):   # if already processed, skip
                i += 1
                continue

            current_request_index = item["request_index"]

            # how many items of the current request index are still left
            amount_of_items_left = 0
            last_item_index = 0
            last_next_item_index = 0
            j = i
            while j < len(flattened_items):
                if flattened_items[j]["is_processed"]:
                    j += 1
                    continue
                else:
                    if flattened_items[j]["request_index"] == current_request_index:
                        # starts at the current_request_index
                        amount_of_items_left += 1
                    else:
                        # the list is sorted. If the index changes, the end of the current request is reached
                        last_item_index = j - 1
                        break

            # the tray the item is on in the warehouse and which will be called (not yet now)
            item_tray = warehouse.locate_item(item["item_name"])
            if (item_tray == None):
                # Volledige request mag niet gedaan worden. Alle orders zouden op stock moeten zijn
                raise Exception("\n\nAlle orders zouden op stock moeten zijn\n\n")
            # find out what items are on the tray
            item_counts = Counter(item.name for item in item_tray.items)

            # The list of items that will be processed by the operator as a batch on the same tray
            items_on_tray = []  # list of indexes in flattened_items
            will_request_finish, items_on_tray = self.will_request_finish(flattened_items, i, item_counts, items_on_tray)

            if will_request_finish and config.AMOUNT_OF_ELEVATORS == 2:
                # The next elevator can already take the second tray
                None   # placeholder






            # the tray the item is on in the warehouse and which will be called (not yet now)
            item_tray = warehouse.locate_item(item["item_name"])
            if (item_tray == None):
                # Volledige request mag niet gedaan worden. Alle orders zouden op stock moeten zijn
                raise Exception("\n\nAlle orders zouden op stock moeten zijn\n\n")

            # find out what items are on the tray
            item_counts = Counter(item.name for item in item_tray.items)

            # you can't process the next request if the current one isn't finished during this batch
            # will all items of the request be processed using the tray?
            items_on_tray = []  # these will be handled when the tray arrives at the operator
            item_counts_copy = item_counts.copy()
            j = i
            while j < len(flattened_items):
                current_item_name = flattened_items[j]["item_name"]

                if flattened_items[j]["is_processed"]:
                    continue
                else:
                    if flattened_items[j]["request_index"] == current_request_index:
                        if item_counts_copy[current_item_name] > 0:
                            # the item is on the tray. process it and remove from the tray
                            items_on_tray.append(j)
                            item_counts_copy[current_item_name] -= 1

            is_request_finished = False
            if amount_of_items_left == len(items_on_tray):
                is_request_finished = True
            if amount_of_items_left < len(items_on_tray):
                raise Exception("\n\nThere can't be more items on the tray than there are left.\n\n")

            # If the request is not finished, the next tray needs to be retrieved, and the next request can't be used
            if is_request_finished:
                # we can already start processing the next request to see if there are items already on the tray
                next_request_index = last_item_index+1




            i += 1

    def will_request_finish(self, flattened_items, i, item_counts, items_on_tray):
        while i < len(flattened_items):
            item = flattened_items[i]

            if item.get("processed"):  # if already processed, skip
                i += 1
                continue

            current_request_index = item["request_index"]

            # how many items of the current request index are still left
            amount_of_items_left = 0
            last_item_index = 0
            j = i
            while j < len(flattened_items):
                if flattened_items[j]["is_processed"]:
                    continue
                else:
                    if flattened_items[j]["request_index"] == current_request_index:
                        # starts at the current_request_index
                        amount_of_items_left += 1
                    else:
                        # the list is sorted. If the index changes, the end of the current request is reached
                        last_item_index = j - 1
                        break

            # you can't process the next request if the current one isn't finished during this batch
            # will all items of the request be processed using the tray?
            items_on_tray = []  # these will be handled when the tray arrives at the operator
            j = i
            while j < len(flattened_items):
                current_item_name = flattened_items[j]["item_name"]

                if flattened_items[j]["is_processed"]:
                    continue
                else:
                    if flattened_items[j]["request_index"] == current_request_index:
                        if item_counts[current_item_name] > 0:
                            # the item is on the tray. process it and remove from the tray
                            items_on_tray.append(j)
                            item_counts[current_item_name] -= 1

            is_request_finished = False
            if amount_of_items_left == len(items_on_tray):
                is_request_finished = True
            if amount_of_items_left < len(items_on_tray):
                raise Exception("\n\nThere can't be more items on the tray than there are left.\n\n")

            # If the request is not finished, the next tray needs to be retrieved, and the next request can't be used
            if is_request_finished:
                # we can already start processing the next request to see if there are items already on the tray
                next_request_index = last_item_index + 1
                will_request_finish, next_items_on_tray = self.will_request_finish(flattened_items, i, item_counts)
                items_on_tray.append(next_items_on_tray)  # update the list

            else:
                # we can't continue to the next request since the current one isn't finished
                return False, items_on_tray



            i += 1


class Elevator(sim.Component):
    def setup(self):
        self.current_level = 0
        self.task = "retrieveTray"  # retrieveTray: bring tray to operator | returnTray: return tray to original place
        self.empty = True;
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
        self.y_position = config.BASE_Y + self.current_level * config.LEVEL_HEIGHT
        self.pause_at_level_time = 2.0  # Tijd om even te pauzeren bij aankomst

        #############################


    def setTarget(self, target_tray, item_name):
        self.target_tray_id = target_tray.ID
        self.target_level = target_tray.level
        self.target_tray_number = target_tray.trayNumber  # is '0' or '1'
        self.item = item_name

    def switchTask(self):
        if self.task == "retrieveTray":
            self.task = "returnTray"
        elif self.task == "returnTray":
            self.task = "retrieveTray"
        else:
            debug_print(f"\n\nERROR: Elevator task is unusual!\n\n")

    def retrieveTray(self):
        # Go to the target level, get or release the item(s)
        # Go to the target level
        start_loc = self.current_level
        start_time = env.now()
        self.empty = True
        debug_print("\nElevator travel event:")
        debug_print(f"Elevator going from level {self.current_level} to level {self.target_level} at time {env.now():.2f}")
        yield from self.move_to_level(self.target_level)
        debug_print(f"Elevator arrived at level {self.target_level} at time {env.now():.2f} and is ready to retrieve the tray\n")

        # Retrieve the tray
        yield self.hold(self.retrieve_time)
        debug_print(f"Tray is loaded on elevator at time {env.now():.2f}")
        self.empty = False
        # Go to the operator
        debug_print("\nElevator travel event:")
        debug_print(f"Elevator going from level {self.current_level} to level {config.OPERATOR_LEVEL} at time {env.now():.2f}")

        # Nieuwe Code Visualisatie
        yield from self.move_to_level(config.OPERATOR_LEVEL)

        debug_print(f"Elevator arrived at level {config.OPERATOR_LEVEL} at time {env.now():.2f}")

        # Present the tray to the operator
        yield self.hold(self.present_time)
        debug_print(f"The tray is ready for the operator at time {env.now():.2f}\n")
        self.empty = True
        # The operator will handle the item and press a button to call the elevator to return the tray
        # The button is calling the function switchTask and restarts the process


    def returnTray(self):
        # The target tray variable should still be correct (it isn't changed in the meantime)
        start_time = env.now()
        start_loc = self.current_level
        self.empty = True;
        # Put the tray back on the elevator
        yield self.hold(self.retrieve_time)
        debug_print(f"\nTray is loaded on elevator at time {env.now():.2f}")

        # Go to the target level
        debug_print("\nElevator travel event:")
        debug_print(f"Elevator going from level {self.current_level} to level {self.target_level} at time {env.now():.2f}")

        # Nieuwe Code Visualisatie
        yield from self.move_to_level(self.target_level)

        debug_print(f"Elevator arrived at level {self.target_level} at time {env.now():.2f} and is ready to return the tray\n")

        # Return the tray into the warehouse
        yield self.hold(self.return_time)
        debug_print(f"Tray is returned to the warehouse at time {env.now():.2f}")

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
        start_y = config.BASE_Y + start_level * config.LEVEL_HEIGHT
        end_y = config.BASE_Y + target_level * config.LEVEL_HEIGHT
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

    def add_item(self, item, tray_id):
        # Ensure tray_id is valid
        if 0 <= tray_id < self.height * 2:  # Ensure tray_id is valid
            # Save the tray_id in the item for easy retrieval
            item.tray_ID = tray_id
            # Add the item
            self.trays[tray_id].add_item(item)
            # debug_print(f"Added '{item}' to Tray {tray_id}.")
            # debug_print(f"New tray: {self.trays[tray_id].items}")
        else:
            debug_print(f"Invalid Tray ID {tray_id}! Must be between 0 and {self.height - 1}.")

    def remove_item(self, item_name, tray_id):
        # Remove an item from a certain tray

        if 0 <= tray_id < self.height:  # Ensure tray_id is valid
            removed_item = self.trays[tray_id].remove_item(item_name)
            # if removed_item is not None:
            #     debug_print(f"Removed '{item_name}' from Tray {tray_id}.")
            return removed_item
        else:
            debug_print(f"Invalid Tray ID {tray_id}! Must be between 0 and {self.height - 1}.")

    def locate_item(self, item_name):
        """ Locate the tray that contains an item with the given name. """
        for tray in self.trays:  # Loop through all trays
            for current_item in tray.items:  # Loop through items in each tray
                if current_item.name == item_name:  # Check if the name matches
                    return tray  # Return the tray that contains the item
        raise Exception(f"Item {item_name} not present in the warehouse.")

class Tray:
    def __init__(self, ID):
        self.ID = ID
        # There are 2 trays for each level
        self.level = (ID - 1) // 2  # i.p.v. ID // 2
        self.trayNumber = (ID - 1) % 2
        self.items = []

    def __str__(self):
        return f"Tray(ID={self.ID})"

    def add_item(self, item):
        self.items.append(item)

    def remove_item(self, item_name):
        for item in self.items:
            if item.name == item_name:
                self.items.remove(item)
                return item
        raise Exception(f"Item '{item_name}' not found in Tray {self.ID}!")

class Item:
    def __init__(self, name):
        self.name = name
        self.tray_ID = None

    def __str__(self):
        return f"Item(name={self.name})"

    __repr__ = __str__  # Make repr use str

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


def fill_warehouse_from_tray_items(tray_items, warehouse):
    for tray_id, items in tray_items.items():
        for item_data in items:
            item_id = item_data["item_id"]
            warehouse.add_item(Item(name=str(item_id)), tray_id=tray_id)


def create_requests_from_grouped_orders(grouped_orders):
    requests = []
    for group in grouped_orders:
        item_names = [str(item_id) for item_id in group]  # Zet ints om naar strings
        requests.append(Request(item_names=item_names))
    return requests


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
        debug_print("X | There was no shape defined!")

    # The total time it took to travel s_tot
    return t_j + t_a + t_v


def initialize_result_files():
    """
    Clears or creates empty result files (JSONL and summary) for the given config.
    Should be called once at the start of the simulation.
    """
    folder_path = os.path.join("main_result_output", config.name)
    os.makedirs(folder_path, exist_ok=True)

    # List of files to reset
    files_to_clear = [
        "picking_times.jsonl",
        "handling_times.jsonl",
        "summary.jsonl"
    ]

    for filename in files_to_clear:
        file_path = os.path.join(folder_path, filename)
        with open(file_path, "w"):  # Opens and immediately truncates
            pass


def log_time(item_code, request_index, time_value, log_type):
    """
    Logs handling or picking time of an item to a JSONL file inside a config-specific folder.
    JSONL because it is memory efficient: just add a new line each time. No need to load the whole file in memory
    useful for large datasets
    """
    folder_path = os.path.join("main_result_output", config.name)
    os.makedirs(folder_path, exist_ok=True)

    filename = f"{log_type}_times.jsonl"
    log_path = os.path.join(folder_path, filename)

    key_name = f"{log_type}_time"  # either 'picking_time' or 'handling_time'

    with open(log_path, "a") as f:
        json.dump({
            "item_code": item_code,
            "request_index": request_index,
            key_name: time_value
        }, f)
        f.write("\n")


def write_summary(average_picking_time, average_handling_time, throughput_items_per_hour, total_orders, total_items):
    """
    Appends summary metrics as a JSON line to summary.jsonl in the config-specific output folder.
    """
    folder_path = os.path.join("main_result_output", config.name)
    os.makedirs(folder_path, exist_ok=True)

    summary_data = {
        "average_picking_time": average_picking_time,
        "average_handling_time": average_handling_time,
        "throughput_items_per_hour": throughput_items_per_hour,
        "total_orders": total_orders,
        "total_items": total_items
    }

    summary_path = os.path.join(folder_path, "summary.jsonl")
    with open(summary_path, "a") as f:
        json.dump(summary_data, f)
        f.write("\n")

    debug_print(f"Summary appended to {summary_path}")

''' ====================== MAIN ====================== '''
# start with empty logging files
initialize_result_files()
for run in range(config.AMOUNT_OF_RUNS):
    # Create the orders, inventory and fill the trays
    order_list, inventory_list, grouped_orders = get_inventory_and_orders(config.hours)
    tray_items = get_tray_filling_from_data(inventory_list, config.TRAY_FILLING_MODE, config.tray_length, config.tray_width, config.max_trays)

    # Variables to calculate the throughput of the system. Divide the total time and count to get the average time per item
    # Easily calculate items per hour using: 3600 / average_time
    # Splitting shared time (= lift movement) between items that were handled as a batch from the same tray is acceptable
    # Since we're working with averages, the values can be added to each run to get a global average (if needed)
    env = sim.Environment(trace=False)  # Create the simulation environment

    # for average pick time
    env.total_picking_time = 0.0
    env.picking_count = 0

    # for average item time
    env.request_start = 0.0     # item_stop - item_start = total time to handle an item or a batch of items
    env.request_stop = 0.0
    env.item_picking_times = []         # list of item times in a batch
    env.total_handling_time = 0.0
    env.item_count = 0
    env.order_count = 0

    # Create the simulation environment
    # env = sim.Environment(trace=False)    # Moved to top of the script to declare global variables

    # Create a state to help with synchronization
    elevator_done = sim.State('elevator_done')

    # Create the components
    warehouse = Warehouse(config.WAREHOUSE_HEIGHT)

    # Add random items to the Warehouse (stock)
    # warehouse.add_item(Item(name="Schroevendraaier"), tray_id=3)
    # warehouse.add_item(Item(name="Schroevendraaier"), tray_id=3)
    # warehouse.add_item(Item(name="Plakband"), tray_id=3)
    # warehouse.add_item(Item(name="Schoen"), tray_id=2)
    # warehouse.add_item(Item(name="test"), tray_id=5)
    # warehouse.add_item(Item(name="Schoen"), tray_id=2)

    fill_warehouse_from_tray_items(tray_items, warehouse)

    # Make requests
    # requests = []
    # requests.append(Request(item_names=["Schroevendraaier", "Schroevendraaier", "Plakband"]))
    # requests.append(Request(item_names=["Schoen"]))
    # requests.append(Request(item_names=["test"]))
    requests = create_requests_from_grouped_orders(grouped_orders)


    # Create an Operator and give it the necessary objects
    # The operator is the only Component that executes its process method from the start
    amount_of_items = sum(len(items) for items in order_list.values())
    operator = Operator(env=env, amount_of_items=amount_of_items)
    elevator = Elevator(env=env)
    if config.AMOUNT_OF_ELEVATORS == 2:
        elevator_2 = Elevator(env=env)

    ########################################################################################
    #Start Visualisatie code
    env.animate(False)

    available_height = env.height() - 2*config.TRAY_HEIGHT  # 20 boven en 20 onder als marge
    config.LEVEL_HEIGHT = available_height / config.WAREHOUSE_HEIGHT
    config.BASE_Y = config.TRAY_HEIGHT + 20
    config.TRAY_HEIGHT = config.LEVEL_HEIGHT * 0.8

    # Visualiseer de trays
    for level in range(config.WAREHOUSE_HEIGHT):
        tray_y = config.BASE_Y + level * config.LEVEL_HEIGHT

        sim.AnimateRectangle(
            (-config.TRAY_WIDTH // 2, -config.TRAY_HEIGHT // 2, config.TRAY_WIDTH // 2, config.TRAY_HEIGHT // 2),
            x=config.TRAY_X_LEFT,
            y=tray_y,
            fillcolor='gray',
            linecolor='black',  # ➜ zwarte rand
            linewidth=1,  # ➜ dunne lijn
            text=f"Level {level}",
            text_anchor="center",
            fontsize=14  # ➜ grotere tekst
        )

        sim.AnimateRectangle(
            (-config.TRAY_WIDTH // 2, -config.TRAY_HEIGHT // 2, config.TRAY_WIDTH // 2, config.TRAY_HEIGHT // 2),
            x=config.TRAY_X_RIGHT,
            y=tray_y,
            fillcolor='gray',
            linecolor='black',  # ➜ zwarte rand
            linewidth=1,  # ➜ dunne lijn
            text=f"Level {level}",
            text_anchor="center",
            fontsize=14  # ➜ grotere tekst
        )
        sim.AnimateRectangle(
            (-config.TRAY_WIDTH // 2, -config.TRAY_HEIGHT // 2, config.TRAY_WIDTH // 2, config.TRAY_HEIGHT // 2),
            x=config.LIFT_X_POSITION,
            y=lambda: elevator.y_position,     # ➜ volgt real-time de positie van de lift
            fillcolor= lambda: "blue" if not elevator.empty else 'red',
            linecolor='black',
            text=lambda: elevator.item if not elevator.empty else "Empty",
            text_anchor="center",
            fontsize=14
        )

    try:
        env.run(3000000)
    except SimulationStopped:
        pass  # Quietly ignore the exception

    # for event in event_log:
    #     debug_print(event)

    debug_print("\n\n============ END ============\n\n")

    # Save the summary information in a json file
    total_items_verify = sum(len(strings) for strings in order_list.values())
    print(f"Total items to verify: {total_items_verify}")

    average_picking_time = env.total_picking_time / env.picking_count
    average_item_time = env.total_handling_time / env.item_count
    item_throughput = 3600 / average_item_time  # items per hour
    write_summary(average_picking_time, average_item_time, item_throughput, env.order_count, env.item_count)

    # Show the average pick time
    print(f"Average pick time: {average_picking_time}")
    print(f"Average item time: {average_item_time}")
    print(f"Item throughput: {3600 / average_item_time:.1f} items per hour")

    print("✅ All files were saved")
