import salabim as sim

# Simulatieparameters
WAREHOUSE_HEIGHT = 4  # Aantal niveaus
OPERATOR_LEVEL = 0  # Niveau waar de operator werkt
SCREEN_CENTER_Y = 500  # Verticale positie van het midden
TRAY_WIDTH = 150  # Breedte van de trays
TRAY_HEIGHT = 40  # Hoogte van de trays
ELEVATOR_WIDTH = 60  # Breedte van de lift
ELEVATOR_HEIGHT = 80  # Hoogte van de lift
LIFT_X_POSITION = 500  # X-positie van de lift
TRAY_X_LEFT = 350  # X-positie voor de linker trays
TRAY_X_RIGHT = 650  # X-positie voor de rechter trays
TWO_TRAY_ROWS = True  # Kies of er één of twee rijen trays zijn


class Elevator(sim.Component):
    def setup(self):
        self.current_level = 0
        self.task = "retrieveTray"  # Ophalen of terugbrengen van trays
        self.travel_speed = 2  # Tijd om 1 verdieping te verplaatsen
        self.target_queue = []  # Wachtrij voor meerdere doelniveaus
        self.passivate()

    def addTarget(self, level):
        self.target_queue.append(level)
        if not self.ispassive():
            return
        self.activate()

    def switchTask(self):
        self.task = "returnTray" if self.task == "retrieveTray" else "retrieveTray"

    def process(self):
        while True:
            if self.target_queue:
                target_level = self.target_queue.pop(0)  # Haal het volgende doelniveau op
                travel_time = abs(target_level - self.current_level) * self.travel_speed
                self.hold(travel_time)
                self.current_level = target_level

                if self.task == "retrieveTray":
                    self.hold(1)  # Simuleer laden
                    self.switchTask()
                else:
                    self.hold(1)  # Simuleer lossen
                    self.switchTask()

                elevator_done.set()
            else:
                self.passivate()


# Simulatie setup
env = sim.Environment(trace=False)

elevator_done = sim.State('elevator_done')

elevator = Elevator()

# Visualisatie instellen
env.animate(True)

# Achtergrond en trays tekenen
for level in range(WAREHOUSE_HEIGHT):
    sim.AnimateRectangle(
        (-TRAY_WIDTH // 2, -TRAY_HEIGHT // 2, TRAY_WIDTH // 2, TRAY_HEIGHT // 2),
        x=TRAY_X_LEFT,
        y=SCREEN_CENTER_Y + (level - WAREHOUSE_HEIGHT // 2) * 80,
        fillcolor='gray',
        text=f"Level {level}")

    if TWO_TRAY_ROWS:
        sim.AnimateRectangle(
            (-TRAY_WIDTH // 2, -TRAY_HEIGHT // 2, TRAY_WIDTH // 2, TRAY_HEIGHT // 2),
            x=TRAY_X_RIGHT,
            y=SCREEN_CENTER_Y + (level - WAREHOUSE_HEIGHT // 2) * 80,
            fillcolor='gray',
            text=f"Level {level}")

# Lift animeren als rechthoek
sim.AnimateRectangle(
    (-ELEVATOR_WIDTH // 2, -ELEVATOR_HEIGHT // 2, ELEVATOR_WIDTH // 2, ELEVATOR_HEIGHT // 2),
    x=lambda: LIFT_X_POSITION,
    y=lambda: SCREEN_CENTER_Y + (elevator.current_level - WAREHOUSE_HEIGHT // 2) * 80,
    fillcolor='blue',text="Lift")

# Simulatie starten
# Lift doorloopt meerdere niveaus in volgorde
# for level in [3, 2, 1, 3]:
#     elevator.addTarget(level)

elevator.addTarget(2)
elevator.addTarget(1)
elevator.addTarget(3)

env.run(till=30)