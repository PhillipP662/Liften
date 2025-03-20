import salabim as sim;

## Eerste voorbeeld objecten
# env = sim.Environment()
# env.animate(True)
# env.modelname("Demo animation classes")
# env.background_color("90%gray")
#
#
#
# sim.AnimatePolygon(spec=(100, 100, 300, 100, 200, 190), text="This is\na polygon")
# sim.AnimateLine(spec=(100, 200, 300, 300), text="This is a line")
# sim.AnimateRectangle(spec=(100, 10, 300, 30), text="This is a rectangle")
# sim.AnimateCircle(radius=60, x=100, y=400, text="This is a cicle")
# sim.AnimateCircle(radius=60, radius1=30, x=300, y=400, text="This is an ellipse")
# sim.AnimatePoints(spec=(100, 500, 150, 550, 180, 570, 250, 500, 300, 500), text="These are points")
# sim.AnimateText(text="This is a one-line text", x=100, y=600)
# sim.AnimateText(
#     text="""\
# Multi line text
# -----------------
# Lorem ipsum dolor sit amet, consectetur
# adipiscing elit, sed do eiusmod tempor
# incididunt ut labore et dolore magna aliqua.
# Ut enim ad minim veniam, quis nostrud
# exercitation ullamco laboris nisi ut
# aliquip ex ea commodo consequat. Duis aute
# irure dolor in reprehenderit in voluptate
# velit esse cillum dolore eu fugiat nulla
# pariatur.
#
# Excepteur sint occaecat cupidatat non
# proident, sunt in culpa qui officia
# deserunt mollit anim id est laborum.
# """,
#     x=500,
#     y=100,
# )
#
# sim.AnimateImage("flowers.jpg", x=500, y=400, width=500, text="Flowers", fontsize=150)
# env.run(env.inf)


## Voorbeeld animatie queus
# class X(sim.Component):
#     def setup(self, i):
#         self.i = i
#
#     def animation_objects(self, id):
#         '''
#         the way the component is determined by the id, specified in AnimateQueue
#         'text' means just the name
#         any other value represents the colour
#         '''
#         if id == 'text':
#             ao0 = sim.AnimateText(text=self.name(), textcolor='fg', text_anchor='nw')
#             return 0, 16, ao0
#         else:
#             ao0 = sim.AnimateRectangle((-20, 0, 20, 20),
#                 text=self.name(), fillcolor=id, textcolor='white', arg=self)
#             return 45, 0, ao0
#
#     def process(self):
#         while True:
#             self.hold(sim.Uniform(0, 20)())
#             self.enter(q)
#             self.hold(sim.Uniform(0, 20)())
#             self.leave()
#
#
# env = sim.Environment(trace=False)
# env.background_color('20%gray')
#
# q = sim.Queue('queue')
#
# qa0 = sim.AnimateQueue(q, x=100, y=50, title='queue, normal', direction='e', id='blue')
# qa1 = sim.AnimateQueue(q, x=100, y=250, title='queue, maximum 6 components', direction='e', max_length=6, id='red')
# qa2 = sim.AnimateQueue(q, x=100, y=150, title='queue, reversed', direction='e', reverse=True, id='green')
# qa3 = sim.AnimateQueue(q, x=100, y=440, title='queue, text only', direction='s', id='text')
#
# sim.AnimateMonitor(q.length, x=10, y=450, width=480, height=100, horizontal_scale=5, vertical_scale=5)
#
# sim.AnimateMonitor(q.length_of_stay, x=10, y=570, width=480, height=100, horizontal_scale=5, vertical_scale=5)
#
# sim.AnimateText(text=lambda: q.length.print_histogram(as_str=True), x=500, y=700,
#     text_anchor='nw', font='narrow', fontsize=10)
#
# sim.AnimateText(text=lambda: q.print_info(as_str=True), x=500, y=140,
#     text_anchor='nw', font='narrow', fontsize=10)
#
# [X(i=i) for i in range(15)]
# env.animate(True)
# env.modelname('Demo queue animation')
# env.run()

# //classe voor Animatie van tekst
# class AnimateMovingText(sim.Animate):
#     def __init__(self):
#         sim.Animate.__init__(self, text="", x0=100, x1=1000, t1=env.now() + 10)
#
#     def y(self, t):
#         return int(t) * 50 + 20
#
#     def text(self, t):
#         return f"{t:0.1f}"
#
#
# env = sim.Environment()
# env.animate(True)
# AnimateMovingText()
# env.run(12)

# // Specificatie kleuren gevisualiseerd
# env = sim.Environment()
# env.show_time(False)
# env.animate(True)
# env.background_color("90%gray")
#
# for i, name in enumerate(sorted(env.colornames())):
#     x = 7 + (i % 6) * 170
#     y = 720 - (i // 6) * 28
#     env.AnimateRectangle(
#         (0, 0, 160, 21),
#         x=x,
#         y=y,
#         fillcolor=name,
#         text=(name, "<null string>")[name == ""],
#         textcolor=("black", "white")[env.is_dark(name)],
#         font="calibribold",
#         fontsize=17,
#         linecolor="black",
#     )
#
# env.run(env.inf)

import salabim as sim

env = sim.Environment()


class X(sim.Component):
    def animation_objects1(self):
        an1 = env.AnimateImage("https://salabim.org/bird.gif", animation_repeat=True, width=50, offsety=-15)
        an2 = env.AnimateText(text=f"{self.sequence_number()}", offsetx=15, offsety=-25, fontsize=13)
        return 50, 50, an1, an2

    def process(self):
        self.enter(env.q)
        self.hold(env.Uniform(5))
        self.leave(env.q)

env.speed(3)
env.background_color(("#eeffcc"))
env.width(1000, True)
env.height(700)
env.animate(True)
env.AnimateImage("https://salabim.org/bird.gif", animation_repeat=True, width=150, x=lambda t: 1000 - 30 * t, y=150)
env.AnimateImage("https://salabim.org/bird.gif", animation_repeat=True, width=300, x=lambda t: 1000 - 60 * t, y=220)
env.AnimateImage(
    "https://salabim.org/bird.gif",
    animation_repeat=True,
    width=100,
    animation_speed=1.5,
    x=lambda t: 0 + 100 * (t - 25),
    y=350,
    animation_start=25,
    flip_horizontal=True,
)
env.AnimateImage("https://salabim.org/bird.gif", animation_repeat=True, width=240, animation_speed=0.5, x=lambda t: 1000 - 50 * t, y=380)
env.AnimateImage("https://salabim.org/bird.gif", animation_repeat=True, width=250, animation_speed=1.3, x=lambda t: 1000 - 40 * t, y=480)

env.q = env.Queue("queue")
env.q.animate(x=700, y=50, direction="w")
env.ComponentGenerator(X, iat=env.Exponential(1.5))
env.run()