from pybricks.hubs import EV3Brick
from pybricks.tools import StopWatch, wait

import properties
from logger import LOGGER, TIMER, Logger
from motor_control import MotorControl
from sensors import Sensors

class DataStorage:
    last_reflection = 0
    reflection_integral = 0

    def add_to_reflection_integral(self, reflection):
        self.reflection_integral += reflection

    action = 0
    def set_action(self, ev3, action):
        self.action = action
        Utils.beep(ev3)
    def is_action(self, action):
        return self.action == action
    class actions:
        WAIT_WALL = 0
        WAIT_WHITE = 1
        WAIT_BLUE = 2
        NONE =  3

class Utils:
    def get_f_x_refleciton():
        return "f(x) = " + str(properties.ReflectionMeasurement.m) + "  * x + " + str(properties.ReflectionMeasurement.c)
    
    def mr(ev3:EV3Brick, watch:StopWatch, sensors:Sensors, controller:MotorControl):
        "measure reflection - blocks execution, prints the values of the reflection from the color sensor"
        while True:
            ev3.screen.clear()
            value = sensors.reflection()
            time = watch.time()
            print(str(time) + "\t" + str(value) + "\t" + str(sensors.reflection_converter(value)))
            ev3.screen.print(str(time))
            ev3.screen.print(str(value))
            wait(100)     
    
    def mrda(ev3:EV3Brick, watch:StopWatch, sensors:Sensors, controller:MotorControl):
        "measure reflection drive area - automatically (setup in 90° to drive direction) drives accross the area"
        print("old function was: " + Utils.get_f_x_refleciton())
        ev3.screen.clear()

        n = 4
        
        values = []
        distance_between_measurement_points = (properties.DriveArea.width - properties.Brick.sensor_width) / (n - 1)
        for i in range(n):
            Utils.beep(ev3)
            value = sensors.reflection()
            time = watch.time()
            
            print(str(i * 100/ (n - 1)) + " " + str(value) + "\t" + str(time))
            ev3.screen.print(str(i) + " " + str(value))

            values.append((
                value,
                i * 100/ (n - 1)
            ))
            if i in range(n - 1):
                controller.change_Δs_relative(distance_between_measurement_points, properties.ReflectionMeasurement.v, True)
        del value, time, distance_between_measurement_points, n

        point_average = lambda a, b: ( (a[0] + b[0]) / 2, (a[1] + b[1]) / 2 )

        values[0] = point_average(values[0], values[1])
        values[1] = point_average(values[2], values[3])
        del point_average

        get_m = lambda a, b: (b[1] - a[1]) / (b[0] - a[0])
        m = get_m(values[0], values[1])
        del get_m

        c = values[0][1] - values[0][1] * m
        del values

        sensors.set_reflection(m, c)
        print("new function is: " + Utils.get_f_x_refleciton())
    
    def mrda_print_only(ev3:EV3Brick, watch:StopWatch, sensors:Sensors, controller:MotorControl):
        n = 20
        distance_between_measurement_points = (properties.DriveArea.width - properties.Brick.sensor_width) / (n - 1)
        print("m = {", end = "")

        for i in range(n):
            Utils.beep(ev3)
            value = sensors.reflection()
            
            print("(" + str(i * 100 / (n - 1)) + "," + str(value) + ")", end = "")

            if i in range(n - 1):
                print(",", end = "")
                controller.change_Δs_relative(distance_between_measurement_points, properties.ReflectionMeasurement.v, True)

        print("}")

    def await_button_release(ev3:EV3Brick, sensors:Sensors):
        while not sensors.is_pressed():
            while not sensors.is_pressed():
                wait(100)
            wait(1000)
        Utils.beep(ev3)
        while sensors.is_pressed():
            wait(100)
        Utils.beep(ev3)

    def shoot_to_min(ev3:EV3Brick, TIMER:StopWatch, sensors:Sensors, controller:MotorControl, LOGGER:Logger):
        max_α = 80
        steps = 34 # we do 34 steps in total, 17 for each side
        shoot_offset = 0 # offset to shoot in drive direction to the side

        ANGLE_PER_STEP = 2 * max_α / steps
        if properties.Brick.skip_shoot:
            angle_to = properties.DriveArea.parabola_angle
            shoot_offset = 0
        else:
            data = []
            for i in range(steps):
                data.append(0)

            controller.angle_absolute(-max_α)

            min_index = 0
            for i in range(steps):
                if not (i is 0):
                    controller.angle_relative(ANGLE_PER_STEP)
                data[i] = sensors.distance()

                if properties.Brick.shoot_correction:
                    data[i] = data[i] + properties.Brick.shoot_correction_function(i)

                print(str(i) + " " + str(data[i]))
                if data[min_index] > data[i]:
                    min_index = i
            
            angle_to = min_index * ANGLE_PER_STEP
            angle_to -= max_α
        controller.angle_absolute(angle_to + shoot_offset)

        if not properties.Brick.skip_shoot:
            print(str(min_index) + " " + str(angle_to) + " " + str(max_α) + " " + str(ANGLE_PER_STEP))
        
        if properties.Brick.shoot:
            Utils.beep(ev3)
            controller.shoot()
        
        controller.angle_absolute(0)

    def main(ev3:EV3Brick, TIMER:StopWatch, sensors:Sensors, controller:MotorControl, LOGGER:Logger, await_release):
        Utils.beep(ev3)

        T = int(1000 / properties.Brick.tps)
        if await_release:
            Utils.await_button_release(ev3, sensors)

        storage = DataStorage()
        storage.set_action(ev3, storage.actions.WAIT_WALL)

        controller.change_v_absolute(properties.DriveSetting.v)
        while not sensors.is_pressed():
            t_start = TIMER.time()
            Utils.tick(ev3, controller, sensors, TIMER, LOGGER, storage)
            Δt = TIMER.time() - t_start
            Δt_wait = T - Δt
            wait(Δt_wait if Δt_wait > 0 else 0)

        Utils.beep(ev3)
        print("last time that tick() took: " + str(Δt))
        controller.stop()
        controller.angle_absolute(0, True)
    
    def tick(ev3:EV3Brick, controller:MotorControl, sensors:Sensors, watch:StopWatch, log:Logger, storage:DataStorage):
        reflection = sensors.reflection_converted() - properties.DriveSetting.center
        last_reflection = storage.last_reflection
        storage.last_reflection = reflection
        storage.add_to_reflection_integral(reflection)
        reflection_integral = storage.reflection_integral

        Δreflection = last_reflection - reflection

        distance = sensors.distance()
        factor = 1
        if storage.action == storage.actions.WAIT_WALL and properties.DriveArea.parabola_in_semicircle:
            if distance < (properties.DriveArea.width * 0.6):
                #print("wall!")
                storage.set_action(ev3, storage.actions.WAIT_WHITE)
        
        if storage.action == storage.actions.WAIT_WHITE:
            factor = 0.8
            if (last_reflection - reflection) < - properties.DriveSetting.from_gradient_to_white:
                #print("white!")
                storage.set_action(ev3, storage.actions.WAIT_BLUE)
            #print(str(reflection))
        
        if storage.action == storage.actions.WAIT_BLUE:
            controller.angle_track(0)
            if sensors.is_blue():
                #print("blue!")
                #controller.stop()
                controller.main_motor.hold()
                controller.change_Δs_relative(5, properties.DriveSetting.v, True)
                
                Utils.beep(ev3)
                Utils.shoot_to_min(ev3, TIMER, sensors, controller, LOGGER)

                properties.DriveSetting.center = 50
                properties.DriveSetting.v += 200
                controller.change_v_absolute(properties.DriveSetting.v)
                storage.set_action(ev3, storage.actions.NONE)
        else:
            controller.angle_track(
                properties.DriveSetting.Kp * factor * reflection +
                properties.DriveSetting.Ki * factor * reflection_integral +
                properties.DriveSetting.Kd * factor * Δreflection
            )
        #print(str(sensors.reflection_converted()))

    def beep(ev3:EV3Brick):
        if not properties.Brick.is_silent:
            ev3.speaker.beep()
