Brief description of the scripts:
=================================

testBoard.py
------------

Launches the GUI. The script simply creates the GUI. The script `testBoardGUI.py` 
handles the workings of the GUI.

Libraries:
`sys`
`PyQt5`

testBoardGUI.py
---------------

Main module for the GUI. This file contains the GUI class that initializes the buttons 
and tabs for the GUI. It also establishes the serial connection, runs the startup 
commands, and handles error dialogs. The version-specific configurations for the 
initialization are sourced from the configuration file from the `config` directory. 
A detailed description of the configuration file is given in the README in the 
`config` directory. 

Libraries:
`PyQt5`
`numpy`

User-created libraries:
`colutaMod`
`serialMod`
`status`
`dataParser`
`monitoring`
`chipConfiguration`
`instrumentControlMod`

colutaMod.py
------------

Module containing assorted helper functions for testboard operation, including 
functions for I2C communication. 

Libraries:
`PyQt5`
`numpy`

User-created libraries:
`serialMod`

serialMod.py
------------

Module that handles the serial communication with the board. The script searches for 
serial ports, connects to the FIFO, and interfaces with the FIFO (read and write).

Libraries:
`serial`
`time`
`platform`
`PyQt5`

status.py
---------

Module for storing, reading, and writing status bits to the on-board FPGA

dataParser.py
-------------

Script which decodes input binary data and saves the decimal data for each channel to 
output data files. It also saves various attributes in the output hdf5 file to help
with offline data analysis. The user can modify this portion of the code to save more
attributes as desired. The script reads a configuration file `dataConfig.cfg` from the 
directory `config`. This configuration file contains board-specific information for 
correctly finding and packaging the output data. 

Libraries:
`h5py`
`numpy`
`configparser`
`collections`
`os`

monitoring.py
-------------

Script which updates the monitoring plots.

Libraries:
`numpy`
`matplotlib`
`PyQt5`

chipConfiguration.py
--------------------

Module which handles configuration bits for each chip, including connecting settings 
to the GUI and loading configuration files.

Libraries:
`PyQt5`
`configparser`

User-created libraries:
`colutaMod`

instrumentControlMod.py
-----------------------

Module which handles communication with external instrumentation, particularly 
external function generators. Must be edited by the user to communicate with their
particular instruments.

Libraries:
`pyVISA`
`PyQt5`
`configparser`

