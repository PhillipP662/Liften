import salabim as sim

# Ensure fully yieldless mode (default is True, but let's be explicit)
sim.yieldless(True)


class Elevator(sim.Component):
    def setup(self):
        self.current_level = 0
        self.target_level = 0
        self.capacity = 4
        self.items = []
        self.travel_time = 2  # Time to move one floor

    def process(self):
        while True:
            self.hold(self.travel_time)  # Travel time between floors
            self.current_level += self.direction
            print(f"Elevator at level {self.current_level} at time {env.now()}")

            # Let passengers off
            for passenger in list(self.items):
                if passenger.target_floor == self.current_floor:
                    self.passengers.remove(passenger)
                    passenger.activate()
                    print(f"{passenger.name()} exited at floor {self.current_floor} at time {env.now()}")

            # Change direction if at top or bottom floor
            if self.current_floor == 5:
                self.direction = -1
            elif self.current_floor == 0:
                self.direction = 1


class Person(sim.Component):
    def setup(self, start_floor, target_floor):
        self.start_floor = start_floor
        self.target_floor = target_floor

    def process(self):
        print(f"{self.name()} arrived at floor {self.start_floor} at time {env.now()}")
        self.hold(1)  # Walking time to elevator

        if len(elevator.passengers) < elevator.capacity:
            elevator.passengers.append(self)
            print(f"{self.name()} entered the elevator at floor {self.start_floor} at time {env.now()}")
            self.passivate()  # Wait inside elevator until arrival
            print(f"{self.name()} reached destination floor {self.target_floor} at time {env.now()}")
        else:
            print(f"{self.name()} could not enter the elevator (full) at time {env.now()}")


# Create the simulation environment
env = sim.Environment(trace=False)

# Create one elevator
elevator = Elevator()

# Create people to use the elevator
for i in range(5):
    Person(start_floor=0, target_floor=3, name=f"Person{i+1}")

# Run the simulation for 30 time units
env.run(till=30)
