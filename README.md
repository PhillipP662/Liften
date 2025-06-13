# OneNote-to-XML


## Pre-requisites
- This project was tested on Python 3.10.11
- Install the requirements.
```bash
pip install -r requirements.txt
```

## GOAL
This project is used to simulate a Vertical Lift Module (VLM) using the Salabim simulation library.

## Simulation
The simulation generates orders and fills the VLM's trays with items.
After that, the Operator starts the process and when the Operator has processed all orders, the simulation ends.

To run the simulation, run 1 of the following scripts:
- Run the regular simulation.
```bash
python salabimElevator.py
```
- Run the simulation using multiprocessing (recommended for multiple runs).
```bash
python salabimElevator_multiprocessing.py
```
- Run the demo simulation to showcase the visualisation.
```bash
python salabimElevator_demo.py
```

The following adaptations can be done:
- Change the configuration: At the line `config = load_config("Configurations/X.yaml")`, use a different YAML-file which can be found in the `Configurations` folder.
- Disable/enable unnecessary print statements: change the parameter `USE_PRINT` at the top of the script.
- Diable/enable visalisation/animation: change the parameter `USE_ANIMATION` at the top of the script.
- The amount of runs (full simulations) can be specified in the used YAML-file.

The datapoints of the picking and handling (processing items) time are collected dynamically using JSONL-files. At the end of each run the collected data van be found in the folder `main_result_output` where the data is in a folder with the name corresponding do the name of the used configuration file.

## Additional files for simulation
Certain functions of the 3 files in the `Dataverwerking_code/for_main` folder are imported into the simulation script and are used to generate the orders, picking times and filling strategies for the trays.
They are required to run the simulation.
Regarding the following scripts:
- Picktijden.py
- Tray_filling.py
- VerdelingBestellingen.py


## Other files
Other files found in this repository were used to experiment code, visualize data, etc. but are not necessary to run the simulation.