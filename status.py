"""Module for storing, reading, and writing status bits

name: status.py
author: C.D. Burton
email: burton@utexas.edu
date: 8 September 2018
"""
import serialMod
import time
class Status:
    """Status class definition."""
    def __init__(self,coluta):
        # general bits
        self.softwareReset = 0
        self.colutaReset = 0
        self.pulseCommand = 0
        self.resetTrigger = 0
        self.readStatus = 0
        # fifo A bits
        self.fifoAOperation = 0
        self.fifoACounter = 0
        self.chipAddress = 0
        # start bits
        self.startFifoAOperation = 0
        self.startControlOperation = 0
        self.startMeasurement = 0

    def read(self):
        # Status words. status1 -> status6
        return [254,
                (self.colutaReset<<5)+(self.chipAddress<<2)+(self.fifoAOperation<<0),
                self.fifoACounter&255,
                self.fifoACounter>>8,
                ((self.readStatus<<7)+\
                 (self.startFifoAOperation<<6)+\
                 (self.softwareReset<<5)+\
                 (self.resetTrigger<<3)+\
                 (self.startMeasurement<<2)+\
                 (self.pulseCommand<<1)+\
                 (self.startControlOperation)),
                255]

    def send(self,coluta):
        integerStatus = self.read()
        serialMod.writeToChip(coluta,'B',integerStatus)

    # Ray Xu Feb 23, 2018: perform coluta reset
    # This is done by bringing status byte 2, bit 5 to high state then back to low state
    # Hard-coded for the time being (radn run)
    def sendColutaReset(self,coluta):
        print('Hard reset ... ')
        # coluta.logger.addEntry('ERROR','HARD RESET')
        self.colutaReset = 1
        self.send(coluta)
        time.sleep(0.1)
        self.colutaReset = 0
        self.send(coluta)

    # Operation functions. Operations are triggered on the rising edge, so one
    # needs to reset the flag after sending the command
    def sendFifoAOperation(self,coluta,operation,counter,address=0):
        # set the bits and flags
        self.fifoAOperation = operation
        self.fifoACounter = counter
        self.startFifoAOperation = 1
        self.chipAddress = address
        # send to the chip
        self.send(coluta)
        # reset the bits and flags
        self.fifoAOperation = 0
        self.fifoACounter = 0
        self.startFifoAOperation = 0
        self.chipAddress = 0

    def sendStartControlOperation(self,coluta,operation=0,address=0):
        self.fifoAOperation = operation
        self.chipAddress = address
        self.startControlOperation = 1
        self.send(coluta)
        self.fifoAOperation = 0
        self.chipAddress = 0
        self.startControlOperation = 0

    def sendStartMeasurement(self,coluta):
        self.startMeasurement = 1
        self.send(coluta)
        self.startMeasurement = 0

    def sendSoftwareReset(self,coluta):
        self.softwareReset = 1
        self.send(coluta)
        self.softwareReset = 0

    def sendI2Ccommand(self,coluta):
        self.startControlOperation = 1
        self.fifoAOperation = 1
        self.send(coluta)
        self.startControlOperation = 0
        self.fifoAOperation = 0

    def updatePulseDelay(self,coluta):
        self.resetTrigger = 1 if coluta.triggerResetTriggerDelayBox.isChecked() else 0
        self.pulseCommand = 1 if coluta.triggerDecrementDelayCounterBox.isChecked() else 0
        self.startMeasurement = 1 
        self.send(coluta)
        self.startMeasurement = 0
        self.resetTrigger = 0
        self.pulseCommand = 0
        
    def initializeUSB(self,coluta):
       integerStatus = [255,255,255,255,255,255]
       serialMod.writeToChip(coluta,'B',integerStatus)

    def readbackStatus(self,coluta):
        self.readStatus = 1
        self.send(coluta)
        self.readStatus = 0 

    def sendCalibrationPulse(self,coluta):
        self.send(coluta)
        self.resetTrigger = 1
        self.startMeasurement = 1
        self.send(coluta)
        self.resetTrigger = 0
        self.startMeasurement = 0 
# end Status