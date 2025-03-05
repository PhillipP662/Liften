import salabim as sim


class Test1(sim.Component):
    def __init__(self, test2, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.test2 = test2
        self.tijd = 0

    def process(self):
        for i in range(3):
            start.reset()
            self.tijd += 1
            self.hold(1)
            self.test2.activate()
            print(f"\nbefore: {env.now()}")
            self.wait(start)
            print(f"after: {env.now()}")


class Test2(sim.Component):
    def setup(self):
        self.tijd = 0
        self.passivate()
    def process(self):
        self.tijd += 1
        self.hold(2)
        start.set()


# Create the simulation environment
env = sim.Environment(trace=False)
start=sim.State('start')

test2 = Test2()
test1 = Test1(test2)
print(f"Test1: {test1.tijd}")
print(f"Test2: {test2.tijd}")

# Run the simulation for 30 time units
env.run(till=10)
print(f"Test1: {test1.tijd}")
print(f"Test2: {test2.tijd}")


