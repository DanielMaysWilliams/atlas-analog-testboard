Control Tab
-----------

__Plot Chip / Plot Channel__: Adjusting these drop down menus allows the user to plot different
 COLUTA output channels during data-taking

__LAUROC Dynamic Range Settings__: The LAUROC pre-amp/shapers can operate with three different
 dynamic ranges. This dropdown menu lets the user easily switch between them 
 
__Load/Save Configuration__: Each chip has it's own default configuration file that is loaded
 when the GUI is launched, but it is possible to save the current set of configurations in the
  GUI, as well as to load a previously saved configuration 

__LpGBT Read/Write Register__: The LpGBT has several hundred configuration registers, and the GUI
 configures a subset of them automatically. If the user wishes to quickly configure a register or
 to see what the current configuration stored in a register is, they can use this portion of the
 GUI. __NB__: The register address value should in decimal, and the read value is printed to
 the command line, not the GUI


LAUROC Tabs
-----------

[__Documentation__](https://www.nevis.columbia.edu/~dawillia/Testboard_documentation/datasheet_Lauroc1_20190506.pdf)

__RC HG S1 et al.__: The shaper portion of the LAUROC is a three stage, CR-RC2 shaper. These
 settings let the user adjust the time constants of each of these stages, as outlined in
 the documentation
  
__DAC VDC LG/HG__: These settings let the user adjust the output voltage baseline of each channel
 of the LAUROC. __NB__: The low gain setting is inverted, so a value of 0 corresponds to the
 baseline at its highest value


LpGBT Tab
---------

[__Documentation__](https://www.nevis.columbia.edu/~dawillia/Testboard_documentation/lpGBT.pdf)

The lpGBT documentation lists a set of "Quick start" configuration bits, which are all 
configurable using the GUI. There are additional configurations available for each of 
the ePorts of the lpGBT that are used on the testboard. A description of each can be 
found in the linked documentation


COLUTA Tabs
-----------

[__Documentation__](https://www.nevis.columbia.edu/~dawillia/Testboard_documentation/COLUTAV2_ds.pdf)

__Gain Select__: Changes the mode of the DRE: on means forced 1x mode, off means forced 4x mode

__Manual Select__: If this setting is on, the DRE is set according to "Gain Select". If it is off, 
the DRE is in "Auto-Gain" mode

__External/DRE to SAR__: If "External to SAR" is selected then the input to the "SAR test input" 
on the board is used. If "DRE to SAR" is selected then the SAR uses the DRE as input


Trigger Tab
-----------

__SPI Instruction__: Controls the voltage produced by the 18-bit DAC of the onboard
pulser. Valid numbers are 0 to 262143, with a maximum output voltage of 4095 mV

__Number of Calibration Pulses per Trigger__: Controls the number of calibration pulses
generated each time a trigger is sent to the onboard pulser, up to a maximum of 31. This 
button must be pressed once after a chip if configured in order to reconfigure the 
correct number of pulses


Instrumentation Tab
-------------------

This tab interfaces with [instrumentControlMod](../instrumentControlMod.py), which must be
rewritten for use with the user's external instrumentation 
