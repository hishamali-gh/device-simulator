import requests

import argparse

import random

import time


TYPE_CHOICES = ['oven', 'conveyor', 'pump']


def get_args():

    parser = argparse.ArgumentParser(description='Pizzeria VDCS Edge Device Simulator') # This creates a 'Parser' object. Think of it like a form. We are defining what fields need to be filled out before the script is allowed to run.

    parser.add_argument('--tenant', required=True, help="Subdomain of the tenant (e.g., futuralabs)")
    parser.add_argument('--id', required=True, help="Unique device UUID")
    parser.add_argument('--type', choices=TYPE_CHOICES, required=True)
    parser.add_argument('--name', required=True)

    return parser.parse_args() # This line gathers all the values you typed in the terminal and bundles them into a single Python object (args).


class DeviceSimulator:
    def __init__(self, tenant, id, type, name):
        self.url = f"http://{tenant}.localhost:8000/devices/ingest/"
        self.device_id = id
        self.type = type
        self.name = name

        self.is_on = True

        self.current_value = self._get_initial_value() # We set an initial 'normal' starting value based on what kind of machine this is.

        self.target_value = self._get_initial_value()


    def _get_initial_value(self): # The underscore (_) at the beginning denotes Functional Encapsulation (hiding logic).
        defaults = {'oven': 400.0, 'conveyor': 0.1, 'pump': 10.0}

        return defaults.get(self.type, 0.0)
    

    def _handle_command(self, command):
        if command == 'SHUTDOWN':
            self.is_on = False

        elif command == 'START':
            self.is_on = True


    def update_state(self, command_payload):
        # This is called when a message comes from Redis

        self.target_value = command_payload.get('value', self.target_value)
        self.is_on = command_payload.get('is_on', self.is_on)


    def simulate_physics(self):
        # Real sensors aren't perfect; they flicker slightly.

        # 1. Define the 'Target' based on Power and Type

        if self.type == 'oven':
            target_value = 450.0 if self.is_on else 70.0 # If the heater is ON, target is 450. If OFF, target is 70 (room temp).

        elif self.type == 'conveyor':
            target_value = 0.5 if self.is_on else 0.0

        else:
            target_value = 12.0 if self.is_on else 0.0


        # 2. Calculate the Difference - How far away are we from the target?

        diff = target_value - self.current_value
        

        # 3. Apply the 'Time Constant' (k)

        k = 0.05 if self.type == 'oven' else 0.5 # Ovens change slowly (k=0.05). Belts change fast (k=0.5).
        

        # 4. We only move a small percentage (k) toward the target each heartbeat.

        self.current_value += (diff * k)
        

        # 5. Add a tiny bit of random noise for the HMI look

        noise = random.uniform(-0.1, 0.1)

        return round(self.current_value + noise, 2)


    def run(self):
        print(f"--- Device {self.name} [{self.type}] started ---")

        try:
            while True:
                value = self.simulate_physics()

                payload = {
                    'device': self.device_id,
                    'type': self.type,
                    'name': self.name,
                    'value': value,
                    'is_on': self.is_on
                }

                try:
                    response = requests.post(self.url, json=payload, timeout=2)

                    if response.status_code == 200:
                        data = response.json()

                        if 'command' in data:
                            self._handle_command(data['command'])

                except requests.exceptions.RequestException as e:
                    print(f"{self.name} Communication Error: {e}")

                time.sleep(2)

        except KeyboardInterrupt:
            print(f"--- Device {self.name} stopped by user ---")


""" In Python, every time you "import" a file, the computer reads it from top to bottom.

Without the safety lock below, simply trying to borrow a piece of logic from your file would cause the whole factory to start running immediately and unintentionally.


Every Python file has a built-in "hidden" variable called __name__. Python automatically fills this variable depending on how the file is being used:

    Scenario A: Running the file directly
        When you type python base_simulator.py in your terminal:

        Python says: "This is the primary file the user wants to run."

        It sets __name__ = "__main__".

        Result: The if statement evaluates to True, and the simulator starts.

    Scenario B: Importing the file
        Imagine you create a new file called factory_manager.py and you want to use the DeviceSimulator class inside it by writing from base_simulator import DeviceSimulator:

        Python says: "I'm just visiting this file to borrow its blueprints."

        It sets __name__ = "base_simulator".

        Result: The if statement evaluates to False. The computer learns how to build a simulator but does not actually start one. """


if __name__ == '__main__':
    args = get_args()

    device = DeviceSimulator(args.tenant, args.id, args.type, args.name) # 'parse_args()' will automatically strip the leading dashes and convert any middle dashes into underscores.

    device.run()
