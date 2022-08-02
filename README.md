This repository contains the source code for the GUI that controls the analog testboard,
an integration test of the readout electronics for the High-Luminosity LHC upgrade to 
the ATLAS Liquid Argon calorimeter.

This readme covers installation and operation of the GUI, as well as some notes/tips. 

Instructions on how to setup the analog testboard itself can be found [here](Readme/Setup.md)

Information on what each python file does can be found [here](Readme/Descriptions.md). 

Quick Setup:
============

To build and install the GUI, please perform the following steps:

1. Download the repository 

`git clone ssh://git@gitlab.cern.ch:7999/cburton/COLUTA65.git`

2. Switch to the `testboard-v1.1` branch (or replace 'testboard-v1.1' with your desired branch)

`git checkout -b testboard-v1.1 origin/testboard-v1.1`

To check if you are in the branch type
`git branch`  and it should tell you which branch you are on. Once you are on the 
branch `testboard-v1.1` create a virtual environment.

3. Create a conda virtual environment.  This only needs to be done once per 
installation instance of Python. Run the following commands in shell to 
generate the environment:

```
conda config --add channels conda-forge
conda create --name coluta python=3 pyserial pyqt numpy matplotlib h5py
conda activate coluta
```

4. Once the environment is installed, it can be activated with the following command

`conda activate coluta`

5. The main script to run the GUI is `testBoard.py`. After activating the virtual 
environment, the GUI can be run with the following command

`python testBoard.py`

Notes for Linux Users
---------------------

1. The user opening the GUI must be added to the usergroup `dialout` to have permissions
to read/write to COM ports.  The computer must be rebooted for changes to take effect.
2. When doing git checkout of a branch, it must be explicitly defined to follow the 
upstream repo.  For example, `git checkout -b <branch name> origin/<branch name>`


Analog Test Board Standard Data Taking Process
===================================================

Configuration
-------------
1. Check board is assembled and cabled correctly following the instructions [here](Readme/Setup.md)
2. Turn on the board power supply and verify that the current draw is normal

| Voltage | Current |
|:-------:|:-------:|
|  +3.6 V |   ~2 A  |
| +10.5 V |  ~20 mA |
|   -7 V  |  ~5 mA  |

3. Verify that the "Clock ok" LED is on 
4. Start GUI using "testBoard.py" with any of the command line options listed below. 
If a timeout error occurs, reseating the USB cable should fix it
5. Press GUI “Configure All” button, wait until configuration process completes. 
This takes about a minute
6. Press GUI “Check Link Ready” button. If the link is not ready, reseat fibre cable on the left 
side of the board and try again, repeating as necessary
7. On the testboard there are various testpoints with voltages printed next to them. When 
the board is powered on and configured for the first time, check these voltages to verify
the board was configured and powered correctly

### Command Line Options ###

`-n` or `--no-connect` runs the GUI without trying to connect to the board. Fills 
the "port" with some `None` types 

`-d` or `--debug` runs the GUI in debug mode. Sets the "debug" flag in the testBoardGUI 
object to `True`, printing out more information as it runs.

`-i` or `--instruments` makes the GUI try to automatically connect to any external 
instrumentation on startup. 
 
Pulser Runs
-----------
1. Place jumpers as shown in [the setup instructions](Readme/Setup.md) to connect the 
 onboard pulser signal
2. In the "Trigger" tab, set "SPI Instruction" to the desired pulse amplitude (this is 
 an 18-bit integer that corresponds to a voltage produced by the onboard DAC) and press 
 "Configure DAC"
3. In the "Trigger" tab, press “Select Calibration Pulses” button ONCE
4. In the "Control" tab ensure the number of readout samples specified in GUI is suitably
 large (4093 is the maximum)
5. In the "Control" tab, press "Trigger Pulser and Take Samples" to take the specified
number of samples
    - In order to take multiple measurements, enter the desired number of measurements in 
    the "Repeat Data Taking" box in the "Control" tab, then press "Trigger Pulser and 
    Take Repeat"
    - In order to take a standard set of measurements for diagnostic purposes, press "Take
     Standard Amplitude Run". Note that this takes upwards of 30 minutes to complete

External AWG Runs
-----------------
1. Place jumpers as shown in [the setup instructions](Readme/Setup.md) to connect an 
 external AWG
2. In the "Instrumentation" tab, press "Initialize Instrument Control" in order to begin
 communication with the external AWG
    - NB: The user must ensure their external AWG is powered on and the computer 
     running the GUI can communicate with it. The user must also edit 
     [instrumentControlMod.py](instrumentControlMod.py) to support their device
3. Once communication with the external AWG is established, enter the desired amplitude 
 (in volts) in the "Pulse Amplitude" box and press "Send Physics Pulse"
4. In the "Control" tab ensure the number of readout samples specified in the GUI is 
 suitably large (4093 is the maximum)
5. In GUI "Control" tab, press "Trigger AWG and Take Samples" to take the specified 
 number of samples
    - In order to take multiple measurements, enter the desired number of measurements in 
     the "Repeat Data Taking" box in the "Control" tab, then press "Trigger AWG and 
     Take Repeat"
                                 
Pedestal Runs                    
-------------
1. Place the jumpers as shown in [the setup instructions](Readme/Setup.md) to take a 
pedestal run
2. Ensure number of readout samples specified in GUI is suitably large (4093)
3. In the "Instrumentation" tab, press the "Initialize" button. Then press "Pedestal" button
4. In the "Control" tab, press "Take Repeat" to record pedestal data

### Note Regarding Various Run Modes ###
It is important to note that the user must ensure that both the hardware configuration 
 of the board and the software configuration of the GUI are correct for their desired 
 run mode. It is possible to e.g. configure the board to take data from an external AWG
 but to press "Trigger Pulser and Take Samples" in the GUI. In this case, the output 
 file's metadata will not accurately describe that measurement
 
 
Additional Configuration Options
--------------------------------
The above sections cover how to get the testboard working in a default state, but there
 are a large number of configuration options available to change in the GUI. A few
 additional options of interest are highlighted [here](Readme/GUIOptions.md).

Useful tips and information:
============================


Installing conda:
-----------------

It is recommended that the user use conda, in the form of miniconda or anaconda, to 
create a virtual environment to run the GUI. Instructions for installing conda can be 
found [here](https://docs.conda.io/projects/conda/en/latest/user-guide/install/index.html).


Git repository download:
------------------------

If the git repository is too large to download, the argument `--depth=1` can be added 
to reduce the size of the download.

`git clone --depth=1 ssh://git@gitlab.cern.ch:7999/cburton/COLUTA65.git`


Channel Mappings:
-----------------

Each chip on the board has various input and output channels, each with its own name 
and going from one chip to the next. Below is a table of what channels are connected 
between each chips:

|        LAUROC Channel        |   COLUTA Channel   |    lpGBT ePort    |
|:----------------------------:|:------------------:|:-----------------:|
| LAUROC 1 Channel 1 Low Gain  | COLUTA 1 Channel 1 | Group 1 Channel 0 |
| LAUROC 1 Channel 1 High Gain | COLUTA 1 Channel 2 | Group 1 Channel 2 |
|                              | COLUTA 1 Frame     | Group 2 Channel 0 |
| LAUROC 2 Channel 2 High Gain | COLUTA 2 Channel 1 | Group 2 Channel 2 | 
| LAUROC 2 Channel 2 Low Gain  | COLUTA 2 Channel 2 | Group 3 Channel 0 | 
|                              | COLUTA 2 Frame     | Group 3 Channel 2 |


Output Data Format:
-------------------

The GUI outputs data in an HDF5 file, with a new file being generated each time the GUI 
is launched (this is referred to as a different _Run_). Within each run's file, the data
is organized as follows:

Root group

Attributes: adc_freq, coluta#_channel#_SAR_weights, n_adcs, n_measurements, serial_number
- Measurement_#
    - Attributes: run_type, awg_freq, laurocDynamicRange, n_samples, pulse_length, 
       <run_type specific attributes>
    - coluta1
        - Attributes: channels
        - channel1
            - Attributes: gain, laurocGain, run_mode
            - raw_data
        - channel2
            - Attributes: gain, laurocGain, run_mode
            - raw_data
    - coluta2
        - Attributes: channels
        - channel1
            - Attributes: gain, laurocGain, run_mode
            - raw_data
        - channel2
            - Attributes: gain, laurocGain, run_mode
            - raw_data
