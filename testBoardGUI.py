"""Main class for the Test Board GUI

name: testBoardGUI.py
author: D. Panchal
email: dpanchal@utexas.edu
date: 13 April 2019
"""
# PyQt libraries
from PyQt5 import uic,QtWidgets,QtCore,QtGui
# from PyQt5.QtCore import QThread
# Python libraries
import numpy as np
import binascii
import time
import glob
import os,sys
# Custom libraries
import colutaMod
import serialMod
from monitoring import MPLCanvas
import chipConfiguration as CC
import configparser
import dataParser
import status
# from logger import Logging
import programClockChip
from datetime import datetime
import instrumentControlMod

qtCreatorFile = colutaMod.resourcePath('testboard.ui')
Ui_MainWindow,QtBaseClass = uic.loadUiType(qtCreatorFile)

class testBoardGUI(QtWidgets.QMainWindow,Ui_MainWindow):
    def __init__(self,qApp,pOptions,pArgs):
        QtWidgets.QMainWindow.__init__(self)
        Ui_MainWindow.__init__(self)

        # General GUI options and signals
        self.qApp = qApp
        self.pOptions = pOptions
        self.pArgs = pArgs
        self.setupUi(self)
        self.setWindowIcon(QtGui.QIcon('./images/cern.png'))
        self.actionQuit.triggered.connect(self.closeConnections)
        self.actionQuit.triggered.connect(qApp.quit)
        self.description = 'TESTBOARDAB'
        # Each chip will have a config file
        self.chips = ['lpgbt','lauroc1','coluta1','coluta2']
        self.lpgbtdefaultConfig   = colutaMod.resourcePath('./config/LpGBT.cfg') # updated configs to see Coluta data 
        # self.lauroc1defaultConfig = colutaMod.resourcePath('./config/LAUROC1.cfg')
        self.lauroc1defaultConfig = colutaMod.resourcePath('./config/LAUROC1_June24.cfg')
        self.coluta1defaultConfig = colutaMod.resourcePath('./config/COLUTA.cfg')
        self.coluta2defaultConfig = colutaMod.resourcePath('./config/COLUTA.cfg')

        self.debug = pOptions.debug
        self.threads = []

        # PySerial connection parameters
        self.baudrate = 1e6
        self.parity = 'N'
        self.stopbits = 1
        self.bytesize = 8
        self.timeout = 2

        # Default attributes for hdf5 output, overwritten by instrument control
        self.runType = 'sine'
        self.sineFrequency = '1.00'
        self.sineAmplitude = '0.50'
        self.awgFreq = 1200 # Sampling freq of external AWG
        self.pulseLength = 64 # Pulse length in bunch crossings

        # Some version-dependent parameters/values
        # These parameters might change for the test board
        self.nSamples = 4093 # default number of samples to parse from standard readout
        self.counter = 8 # Inital number of 32-bit words from the dual port memory
        self.dacFullScale = 1.2 # volts (measured)
        self.discarded = 0 # first N samples of readout are discarded by software (MSB end)
        self.dataWords = 32 # number of bytes for each data FPGA counter increment
        self.dualPortBufferDepth = 4095 # max number of samples 
        self.controlWords = 8 # number of bytes for each control FPGA counter increment
        self.frequency = 40 # MHz clock frequency
        # Instance of the Status class. Communicates with FIFO B.
        self.status = status.Status(self)

        # Instance of the DataParser class.
        dataParserConfig = colutaMod.resourcePath('./config/dataConfig.cfg')
        self.ODP = dataParser.dataParser(self,dataParserConfig)

        # Configurations for each chip
        self.lpgbtConfigurations   = {}
        self.coluta1Configurations = {}
        self.coluta2Configurations = {}
        self.lauroc1Configurations = {}
        self.lauroc2Configurations = {}
        # print(self.lpgbtdefaultConfig)
        self.LpGBTcfgFile = self.lpgbtdefaultConfig
        self.setupConfigurations(self.lpgbtConfigurations,self.LpGBTcfgFile,tabName='lpgbt')

        self.LAUROC1cfgFile = self.lauroc1defaultConfig
        self.setupConfigurations(self.lauroc1Configurations,self.LAUROC1cfgFile,tabName='lauroc1')

        self.LAUROC2cfgFile = self.lauroc1defaultConfig
        self.setupConfigurations(self.lauroc2Configurations,self.LAUROC2cfgFile,tabName='lauroc2')

        self.coluta1cfgFile = self.coluta1defaultConfig
        self.setupConfigurations(self.coluta1Configurations,self.coluta1cfgFile,tabName='coluta1')

        self.coluta2cfgFile = self.coluta2defaultConfig
        self.setupConfigurations(self.coluta2Configurations,self.coluta2cfgFile,tabName='coluta2')

        # # Connection/initialization buttons signal responses
        self.connectButton.clicked.connect(self.reset)
        self.scanComButton.clicked.connect(lambda:serialMod.findPorts(self))
        self.coluta1ConfigFileOpenButton.clicked.connect(lambda:colutaMod.openFileDialog(self,'coluta1'))
        self.coluta1ConfigFileSaveButton.clicked.connect(lambda:CC.writeCfgFile(self,'coluta1'))
        self.coluta2ConfigFileOpenButton.clicked.connect(lambda:colutaMod.openFileDialog(self,'coluta2'))
        self.coluta2ConfigFileSaveButton.clicked.connect(lambda:CC.writeCfgFile(self,'coluta2'))
        self.lauroc1ConfigFileOpenButton.clicked.connect(lambda:colutaMod.openFileDialog(self,'lauroc1'))
        self.lauroc1ConfigFileSaveButton.clicked.connect(lambda:CC.writeCfgFile(self,'lauroc1'))
        self.lpgbtConfigFileOpenButton.clicked.connect(lambda:colutaMod.openFileDialog(self,'lpgbt'))
        self.lpgbtConfigFileSaveButton.clicked.connect(lambda:CC.writeCfgFile(self,'lpgbt'))
        self.takeSamplesButton.clicked.connect(lambda: self.takeSamples())
        self.takeSamplesRepeatButton.clicked.connect(self.takeSamplesRepeat)
        self.takeAWGSamplesRepeatButton.clicked.connect(self.takeAWGSamplesRepeat)
        self.triggerTakeSamplesButton.clicked.connect(self.sendAFGPulseTakeSamples)
        self.sendPulseTakeSamplesBox.clicked.connect(self.sendPulseTakeSamples)
        self.takePulserSamplesRepeatButton.clicked.connect(self.takePulserSamplesRepeat)
        self.standardAmplitudesTakeSamplesBox.clicked.connect(self.takeStandardAmplitudes)
        self.standardAwgRun.clicked.connect(self.takeStandardAwg)
        self.pedestalRunBox.clicked.connect(self.takePedestal)
        # other buttons
        self.nSamplesBox.textChanged.connect(self.updateNSamples)
        self.sendCalibrationPulseBox.clicked.connect(lambda:self.status.sendCalibrationPulse(self))
        self.selectCalibrationPulseBox.clicked.connect(lambda:self.selectI2CinterfaceAndCalPulses())
        self.checkLinkReadyButton.clicked.connect(self.checkLinkReady)
        self.sendExternalTriggerButton.clicked.connect(self.sendExternalTrigger)
        self.configureDynamicRangeButton.clicked.connect(self.configureLAUROCDynamicRange)
        self.configureAllButton.clicked.connect(self.configureAll)

        SUC = self.sendUpdatedConfigurations
        # self.tabWidget.currentChanged.connect(SUC)
        self.configureLpGBTButton.clicked.connect(SUC)
        self.configureLpGBTButton2.clicked.connect(SUC)
        self.configureLpGBTButton3.clicked.connect(SUC)
        self.configureLpGBTButton4.clicked.connect(SUC)
        self.configureLpGBTButton5.clicked.connect(SUC)
        self.coluta1ch1ConfigureButton.clicked.connect(SUC)
        self.coluta2ch1ConfigureButton.clicked.connect(SUC)
        self.coluta1ch2ConfigureButton.clicked.connect(SUC)
        self.coluta2ch2ConfigureButton.clicked.connect(SUC)
        self.coluta1globalConfigureButton.clicked.connect(SUC)
        self.coluta2globalConfigureButton.clicked.connect(SUC)

        # Instrument control buttons
        self.initializeInstrumentButton.clicked.connect(lambda:instrumentControlMod.initializeInstrumentation(self))

        # Temp fix to connect the configure buttons to configureLAUROC() function
        # Need to rewrite fifoAWriteControl() to send LAUROC and DAC configs
        # Tab changes __will__ not send LAUROC configurations!        
        self.lauroc1ConfigureSlowControlButton.clicked.connect(lambda: self.configureLAUROC('slowcontrol'))
        self.lauroc1ConfigureProbeRegisterButton.clicked.connect(lambda: self.configureLAUROC('proberegister',selectFlag='0'))
        self.lauroc2ConfigureSlowControlButton.clicked.connect(lambda:self.configureLAUROC('slowcontrol'))
        self.lauroc2ConfigureProbeRegisterButton.clicked.connect(lambda:self.configureLAUROC('proberegister',selectFlag='0'))

        self.linkResetPulseButton.clicked.connect(lambda:self.LpGBTControl(linkResetPulse='1'))

        self.loadSamplesButton.clicked.connect(self.test)
        # self.configureDACButton.clicked.connect(self.configureDAC)
        self.configureDACButton.clicked.connect(self.configureAndReadBackDAC)
        self.writeRegisterButton.clicked.connect(lambda:colutaMod.i2cWriteLpGBT(self))
        self.readRegisterButton.clicked.connect(lambda:print(colutaMod.i2cReadLpGBT(self)))

        copyConfig = lambda w,x,y,z : lambda : self.copyConfigurations(w,x,chips=y,channels=z)
        self.allCopyConfigButton.clicked.connect(copyConfig('coluta1','ch1',['coluta1','coluta2'],['ch1','ch2']))
        self.coluta1ch2CopyConfigButton.clicked.connect(copyConfig('coluta1','ch1',['coluta1'],['ch2']))
        self.coluta2ch1CopyConfigButton.clicked.connect(copyConfig('coluta1','ch1',['coluta2'],['ch1']))
        self.coluta2ch2CopyConfigButton.clicked.connect(copyConfig('coluta1','ch2',['coluta2'],['ch2']))
        self.coluta2ch2CopyConfigButton_2.clicked.connect(copyConfig('coluta2','ch1',['coluta2'],['ch2']))
        self.lauroc1ScCopyConfigButton.clicked.connect(copyConfig('lauroc1','slowcontrol',['lauroc2'],['slowcontrol']))
        self.lauroc1ProbeCopyConfigButton.clicked.connect(copyConfig('lauroc1','proberegister',['lauroc2'],['proberegister']))

        self.connectButtons(self.lpgbtConfigurations)
        self.connectButtons(self.lauroc1Configurations)
        self.connectButtons(self.lauroc2Configurations)
        self.connectButtons(self.coluta1Configurations)
        self.connectButtons(self.coluta2Configurations)

        # Plotting
        self.dataDisplay = MPLCanvas(self.dataDisplayWidget,x=np.arange(2),style='r.',
                                                ylim=[0,65536],ylabel='ADC Counts')
        self.displayGridLayout.addWidget(self.dataDisplay,0,0)
        self.fftDisplay = MPLCanvas(self.fftDisplayWidget,x=np.arange(2),style='r-',
                                               ylim=[-150,0],ylabel='PSD [dB]',xlabel='Freq. [MHz]')
        self.displayGridLayout.addWidget(self.fftDisplay,1,0)
        # Startup
        self.isConnected = False
        self.startup()
        self.updateStatusBar()
    # end __init__

    def test(self):
        """Test function attached the the load samples button"""
        # print(self.coluta2Configurations.keys())
        # print('new value', self.coluta2Configurations['ch1'].getConfiguration('DriveStrength'))
        # self.fifoAWriteControl('coluta2','global')
        # self.i2cWriteControl(fifoOperation=1,auxRegAddress=1)
        # colutaMod.i2cReadLpGBT(self)
        # self.status.initializeUSB(self)
        # self.status.initializeUSB(self)
        # self.status.send(self)
        # self.status.sendSoftwareReset(self)
        # for catName in self.lpgbtConfigurations:
        #     print(catName, '{0:03x}'.format(self.lpgbtConfigurations[catName].address),
        #           '{0:02x}'.format(int(str(self.lpgbtConfigurations[catName].bits),2)))
        #     # colutaMod.i2cWriteLpGBT(self, 'lpgbt', catName)
        #     colutaMod.i2cWrite(self, 'lpgbt', catName)
        # self.configureLAUROC()
        # print('LAUROC2')
        # self.configureLAUROC('lauroc2')
        # colutaMod.i2cReadBack(self,'coluta1','ch1',i2cAddress=0)
        
        #### Read back status register ####
        # serialMod.flushBuffer(self)
        # self.status.readbackStatus(self)
        # time.sleep(0.1)
        # serialMod.readFromChip(self,'A',6)
        # self.status.send(self)
        #### End read back status register ####
        # self.configureColuta('coluta2')
        # self.configureColuta('coluta2')
        # self.configureLpGBT()
        # self.readLpGBT('clkgconfig0')
        # self.readLpGBT('eptx33chncntr')
        # self.readLpGBT('ldconfigh')
        # self.readLpGBT('powerup2')

        # self.configureLAUROC()
        # self.configureDAC()
        # print(int(self.controlLpGBTRegisterAddressBox.toPlainText()))
        # colutaMod.i2cWriteLpGBT(self,lpgbtRegAddress=453,dataWord='10100011') # register value A3, default 
        # colutaMod.i2cReadLpGBT(self,lpgbtRegAddress=453)

        # self.LpGBTControl()
        # self.checkLinkReady()
        # self.linkResetPulse()
        # self.bunchcrossingControl()
        # self.laurocReadBack()
        # self.sendExternalTrigger()
        # self.sendAFGPulseTakeSamples()
        # self.configureLAUROCDynamicRange()
        # print(self.runType)
        # self.LpGBTControl(lpgbtMode='1000')
        # self.LpGBTControl()
        # for register in range(320,463):
        # for register in range(440,463):
        #     print('{0:03x}'.format(register), colutaMod.i2cReadLpGBT(self, lpgbtRegAddress=register))
        print(self.dacReadBack())


    def startup(self):
        """Runs the standard startup routine."""
        if self.pOptions.no_connect:
            # Dummy startup routine if testing without board
            self.port = 'Placeholder A'
            self.serial = None
            self.serial_number = None
        else:
            # Real startup routine when board is connected
            # Find the port and store the names
            portDict = serialMod.findPorts(self)
            self.port = portDict['AB']
            # Set up the serial connections to each port, pause, and test
            self.serial = serialMod.setupSerials(self)
            time.sleep(0.01)
            self.handshake()
            # Reset the status bits to zero, then reset the FPGA
            self.status.initializeUSB(self)
            self.status.send(self)
            self.status.sendSoftwareReset(self)
            colutaMod.i2cInitCommand(self)
            self.status.send(self)
            self.LpGBTControl(lpgbtRstb='1',linkResetPulse='0')
            time.sleep(0.1)
            self.LpGBTControl(lpgbtRstb='0',linkResetPulse='0')
            time.sleep(0.1)
            self.LpGBTControl(lpgbtRstb='1',linkResetPulse='0')
            #self.sendUpdatedConfigurations()
            self.status.send(self)
            self.configureDAC(startup=True)
            self.configureLAUROCinit()
            self.bunchcrossingControl()

            # Set up connections to instrumentation
            if self.pOptions.instruments:
                # self.IC and self.function_generator are set within iCMod
                instrumentControlMod.initializeInstrumentation(self)
                self.IPaddress = self.ipAddressBox.toPlainText()
            else:
                self.IC,self.function_generator = None,None

        # Update the text boxes
        # self.fifoText.setText(self.port)
        self.fifoText.setText(self.serial_number)

    def handshake(self):
        """Checks that the serial connections. Gives green status to valid ones."""
        self.isConnected = serialMod.checkSerials(self)
        if self.isConnected:
            self.fifoStatusBox.setStyleSheet('background-color: rgb(0, 255, 0);')
            self.fifoStatusBox.setText('Connected')

    def reset(self):
        """Resets the GUI."""
        self.updateStatusBar('Resetting GUI')
        self.updateStatusBar('Applying default configurations')

        self.closeConnections()
        self.fifoStatusBox.setStyleSheet('background-color: rgb(255, 0, 0);')
        self.fifoStatusBox.setText('Not Connected')
        del self.port
        

        self.lpgbtConfigurations.clear()
        self.lauroc1Configurations.clear()
        self.lauroc2Configurations.clear()
        self.coluta1Configurations.clear()
        self.coluta2Configurations.clear()
        
        self.LpGBTcfgFile = self.lpgbtdefaultConfig
        self.setupConfigurations(self.lpgbtConfigurations,self.LpGBTcfgFile,tabName='lpgbt')
        
        self.LAUROC1cfgFile = self.lauroc1defaultConfig
        self.setupConfigurations(self.lauroc1Configurations,self.LAUROC1cfgFile,tabName='lauroc1')

        self.LAUROC2cfgFile = self.lauroc1defaultConfig
        self.setupConfigurations(self.lauroc2Configurations,self.LAUROC2cfgFile,tabName='lauroc2')
        
        self.coluta1cfgFile = self.coluta1defaultConfig
        self.setupConfigurations(self.coluta1Configurations,self.coluta1cfgFile,tabName='coluta1')
        
        self.coluta2cfgFile = self.coluta2defaultConfig
        self.setupConfigurations(self.coluta2Configurations,self.coluta2cfgFile,tabName='coluta2')
        self.startup()
        self.updateStatusBar('Applied default configurations')
        self.updateStatusBar()

    def closeConnections(self):
        """Close connection to serial ports."""
        if self.serial is not None and self.serial.isOpen():
            self.serial.close()

        self.isConnected = False

    def updateStatusBar(self,message='Ready',*args,**kwargs):
        """Updates the status bar on the GUI frontpage"""
        if colutaMod.isMainThread():
            self.statusBar.showMessage('Run '+str(self.ODP.runNumber).zfill(4)+' - '+message,*args,**kwargs)

    def showError(self,message):
        """Error message method. Called by numerous dependencies."""
        if colutaMod.isMainThread():
            errorDialog = QtWidgets.QErrorMessage(self)
            errorDialog.showMessage(message)
            errorDialog.setWindowTitle("Error")

    def fifoAWriteControl(self,chip,categoryName,reset=False):
        '''Write status commands for the requested category for the chip'''
        # MAJOR REWRITE NEEDED
        configurations = getattr(self,chip+'Configurations')
        category = configurations[categoryName]
        address = category.address
        bits = category.bits
        nBit = len(bits)
        if nBit%self.controlWords is not 0:
            # self.showError('Invalid number of control bits: {} requested'.format(nBit))
            # return False
            bits = bits.zfill(int(np.ceil(nBit/self.controlWords)*self.controlWords))
            nBit = len(bits)
        nByte = int(nBit/8)
        # Reverse byte order (but preserve bit order inside byte)
        bitsList = [bits[i:i+8] for i in range(0, len(bits), 8)]
        bitsList.reverse()
        bits = "".join(bitsList)
        # N.B. "sendFifoAOperation" args are (GUI,operation,counter,address)
        # operaton '1' is control register write
        self.status.sendFifoAOperation(self,1,nByte,address)
        serialResult = serialMod.writeToChip(self,'A',bits)
        self.status.sendStartControlOperation(self,1,address)
        if reset: # reset the status bits again
            self.status.send(self)
        return serialResult

    def fifoAReadControl(self,chip,categoryName):
        '''Reads control bits from the requested category of the chip'''
        configurations = getattr(self,chip+'Configurations')
        category = configurations[categoryName]
        address = category.address
        nControlBits = category.total
        if nControlBits%self.controlWords is not 0:
            # self.showError('Invalid number of control bits: {} requested'.format(nControlBits))
            # return False
            nControlBits = int(np.ceil(nControlBits/self.controlWords)*self.controlWords)
        nControlBytes = int(nControlBits/self.controlWords)
        serialMod.flushBuffer(self)
        # FIFO A operation code 2 indicates a control register read.
        self.status.sendFifoAOperation(self,2,nControlBytes,address)
        controlBits = serialMod.readFromChip(self,'A',nControlBits)
        if not isinstance(controlBits,bool):
            controlBits = controlBits[:nControlBytes]
        else:
            controlBits = bytearray(0)
        # Reverse the order of the control bits to match with the config file
        controlBits.reverse()
        self.status.send(self)
        bytesToString = colutaMod.byteArrayToString(controlBits)
        return bytesToString
        # return colutaMod.byteArrayToString(controlBits)

    def laurocReadBack(self):
        serialMod.flushBuffer(self)
        self.status.sendFifoAOperation(self,2,3,3)
        nControlBytes = 48
        controlBits = serialMod.readFromChip(self,'A',nControlBytes*8)
        if not isinstance(controlBits,bool):
            controlBits = controlBits[:nControlBytes]
        else:
            controlBits = bytearray(0)
        self.status.send(self)
        bytesToString = colutaMod.byteArrayToString(controlBits)
        print(bytesToString)

    def dacReadBack(self):
        maxIter = 5
        counter = 0
        bytesToString = None
        nControlBits = 24
        nControlBytes = int(nControlBits / self.controlWords)
        while not bytesToString and counter<maxIter:
            serialMod.flushBuffer(self)
            self.status.sendFifoAOperation(self,2,3,2)
            controlBits = serialMod.readFromChip(self,'A',nControlBits)
            if not isinstance(controlBits,bool):
                controlBits = controlBits[:nControlBytes]
            else:
                controlBits = bytearray(0)
            self.status.send(self)
            bytesToString = colutaMod.byteArrayToString(controlBits)
            counter += 1
            time.sleep(0.5)
        return [bytesToString[i*8:(i+1)*8] for i in range(nControlBytes)][::-1]

    def configureAndReadBackDAC(self):
        self.configureDAC()
        self.configureDAC()
        readBack = ''.join(self.dacReadBack())

        SPIInstruction_int = int(self.controlSPIInstructionBox.toPlainText())
        SPIInstruction = '{:024b}'.format(SPIInstruction_int)

        if SPIInstruction != readBack:
            self.showError("DAC: Did not read back SPI instruction that was written\n"
                           f"Wrote: {SPIInstruction}\n"
                           f"Read back: {readBack}\n"
                           "If this problem persists, power cycle the board"
                           )

    def isLinkReady(self):
        maxIter = 5
        counter = 0
        bytesToString = None
        while not bytesToString and counter<maxIter:
            serialMod.flushBuffer(self)
            self.status.sendFifoAOperation(self,2,1,4)
            nControlBits = 8
            nControlBytes = int(nControlBits/self.controlWords)
            controlBits = serialMod.readFromChip(self,'A',nControlBits)
            if not isinstance(controlBits,bool):
                controlBits = controlBits[:nControlBytes]
            else:
                controlBits = bytearray(0)
            self.status.send(self)
            bytesToString = colutaMod.byteArrayToString(controlBits)
            counter += 1
            time.sleep(0.5)
        print(bytesToString)
        if bytesToString:
            isReady = bytesToString[4]=='1'
        else:
            isReady = False
        return isReady

    def checkLinkReady(self):
        if self.isLinkReady():
            self.linkReadyStatusBox.setStyleSheet('background-color: rgb(0, 255, 0);')
            self.linkReadyStatusBox.setText('Link Ready')
        else:
            self.linkReadyStatusBox.setStyleSheet('background-color: rgb(255, 0, 0);')
            self.linkReadyStatusBox.setText('Link Not Ready')


    def linkResetPulse(self):
        isReady = self.isLinkReady()
        maxAttempts = 25
        counter = 0
        while not isReady and counter < maxAttempts:
            self.LpGBTControl(linkResetPulse='1')
            time.sleep(0.5)
            isReady = self.isLinkReady()
            counter += 1
        if isReady:
            print('big success')
            print(counter)

    def fifoAReadData(self,nSamples):
        """Requests measurement, moves data to buffer, and performs read operation"""

        # 1) Send a start measurement command to the chip
        # 2) Clear the serial buffer (MANDATORY!!!!!) 
        # 3) Fill the serial buffer with data from the chip
        # 4) Read the data filled in the serial buffer
        address = 1 # LpGBT address
        self.status.send(self) # reset the rising edge
        self.status.sendStartMeasurement(self)
        serialMod.flushBuffer(self) # not sure if we need to flush buffer, D.P.
        # One analog measurement will return 16 bytes, thus ask for 2*number of samples requested
        self.status.sendFifoAOperation(self,2,int(2*(self.discarded+self.nSamples)),address=address)
        time.sleep(0.01) # Wait for data to be filled in the USB buffer
        dataByteArray = serialMod.readFromChip(self,'A',self.dataWords*(self.discarded+self.nSamples)) 
        # dataByteArray = serialMod.readFromChip(self,'A',14)
        self.status.send(self) # reset the rising edge
        # return dataByteArray
        first = self.discarded*self.dataWords
        last = (self.discarded+self.nSamples)*self.dataWords
        return dataByteArray[first:last]
    
    def updateNSamples(self):
        try:
            self.nSamples = int(self.nSamplesBox.toPlainText())
            if self.nSamples==self.dualPortBufferDepth+1:
                self.nSamples = 2047.5
            elif self.nSamples > self.dualPortBufferDepth+2:
                self.showError('ERROR: Exceeded maximum number of samples. Max value: 4096.')
                self.nSamples = 2047.5
        except Exception:
            self.nSamples = 0

    def takeSamples(self,doDraw=True):
        """Read and store output data from LpGBT buffer"""

        doFFT = self.doFFTBox.isChecked()
        saveHDF5 = self.saveHDF5Box.isChecked()
        csv = self.saveCSVBox.isChecked()
        # Take data and read from the FPGA
        if not self.isConnected and not self.pOptions.no_connect:
            self.showError('Chip is not connected.')
            return
        self.updateStatusBar('Taking data')
        self.measurementTime = datetime.now().strftime("%y_%m_%d_%H_%M_%S.%f")
        
        # Read the data
        print("Reading data")
        dataByteArray = self.fifoAReadData(self.nSamples)

        if self.pOptions.no_connect: return
        self.updateStatusBar('Writing data')
        # Display the data on the GUI window in groups of 32 bits and in groups on 16 bits on the 
        # terminal window for Jaro
        dataString = colutaMod.byteArrayToString(dataByteArray)
        dataStringByteChunks = "\n".join([dataString[i:i+32] for i in range(0,len(dataString),32)])
        dataStringByteChunks16 = "\n".join([dataString[i:i+16] for i in range(0,len(dataString),16)])
        if self.debug: print(dataStringByteChunks16)
        self.controlTextBox.setPlainText(dataStringByteChunks)

        self.ODP.parseData('coluta',self.nSamples,dataString)
        self.ODP.writeDataToFile(writeHDF5File=saveHDF5,writeCSVFile=csv)

        plotChip = self.plotChipBox.currentText().lower()
        plotChannel = self.plotChannelBox.currentText()
        channelsRead = getattr(self.ODP,plotChip).getSetting('data_channels')
        # channelsRead = ['channel2','channel1']

        self.dataDisplay.resetData()
        self.fftDisplay.resetData()

        if doDraw and plotChannel in channelsRead:
            decimalDict = getattr(self.ODP,plotChip+'DecimalDict')
            adcData = decimalDict[plotChannel]
            self.dataDisplay.updateFigure(adcData,np.arange(len(adcData)))
            if doFFT:
                freq,psd,QA = colutaMod.doFFT(self,adcData)
                QAList = [plotChannel.upper(),
                          'ENOB: {:2f}'.format(QA['ENOB']),
                          'SNR: {:2f} dB'.format(QA['SNR']),
                          'SFDR: {:2f} dB'.format(QA['SFDR']),
                          'SINAD: {:2f} dB'.format(QA['SINAD'])]
                QAStr = '\n'.join(QAList)
                self.controlTextBox.setPlainText(QAStr)
                self.fftDisplay.updateFigure(psd,freq)

        self.updateStatusBar()

    def takeSamplesRepeat(self):
        """Repeats data taking N times without sending trigger"""
        try:
            nReads = int(self.repeatDataBox.toPlainText())
        except:
            self.showError('Invalid entry in repeat data box')
            return
        for i in range(nReads):
            self.takeSamples()
            time.sleep(0.1)
        print("Done taking repeat samples")

    def takeAWGSamplesRepeat(self):
        """Repeats data taking N number of times"""
        try:
            nReads = int(self.repeatDataBox.toPlainText())
        except:
            self.showError('Invalid entry in repeat data box')
            return
        if self.pOptions.instruments:
            for i in range(nReads):
                self.sendAFGPulseTakeSamples()
                time.sleep(0.1)
            print("Done taking repeat samples")
        else:
            self.showError("ERROR: No external AWG found")
            return

    def takePulserSamplesRepeat(self):
        """Repeats data taking N number of times"""
        try:
            nReads = int(self.repeatDataBox.toPlainText())
        except:
            self.showError('Invalid entry in repeat data box')
            return
        self.configureDAC()
        for i in range(nReads):
            self.sendPulseTakeSamples()
            time.sleep(0.1)
        self.configureDAC(reset=True)
        print("Done taking repeat samples")

    def takeStandardAmplitudes(self):
        '''Takes 100 measurements each at a standard set of amplitudes'''
        standardAmps_low = ['0','128','256','384','512','640','768','896','1024','1366','1706']
        standardAmps_high = ['2048','4096','8192','16384','24576','32768','43690','54612','65536']
        self.repeatDataBox.document().setPlainText('36')
        for amp in standardAmps_low :
            print(f'Starting DAC setting {amp} measurements')
            self.controlSPIInstructionBox.document().setPlainText(amp)
            self.configureDAC()
            self.takePulserSamplesRepeat()
        print('Done taking low standard amplitudes')
        for amp in standardAmps_high:
            print(f'Starting DAC setting {amp} measurements')
            self.controlSPIInstructionBox.document().setPlainText(amp)
            self.configureDAC()
            self.takePulserSamplesRepeat()
        print('Done taking high standard amplitudes')

    def takeStandardAwg(self):
        #standardAmps = ['0.03','0.035','0.04','0.045','0.05','0.055','0.06','0.07','0.08','0.09','0.1','0.12','0.14','0.16','0.18','0.2','0.3','0.4','0.5','0.6','0.7','0.8','0.9','1.0']
        #standardAmps = ['0.3','0.35','0.4','0.45','0.5','0.55','0.6','0.65','0.7','0.75','0.8','0.85','0.9','0.95','1.0','2.0','3.0','4.0','5.0','6.0']
        standardAmps = ['0.1','0.2','0.3','0.4','0.5','1.0','2.0','3.0','4.0','5.0','6.0']
        #standardAmps = ['5.0','6.0'] #test
        self.repeatDataBox.document().setPlainText('100')
        for amp in standardAmps :
            print(f'Starting AWG setting {amp} measurements')
            self.pulse_amplitudeBox.document().setPlainText(amp)
            self.function_generator.applyPhysicsPulse()
            self.takeAWGSamplesRepeat()
            time.sleep(0.1)
        print('Done taking AWG')

    def takePedestal(self):
        try:
            nReads = int(self.repeatDataBox.toPlainText())
        except:
            self.showError('Invalid entry in repeat data box')
            return
        self.runType = 'pedestal'
        for i in range(nReads):
            self.takeSamples()
        print("Done taking repeat pedestal")

    def selectI2Cinterface(self,fifoOperation,auxRegAddress,reset=False):
        """Initialize the correct auxiliary register before sending i2c commands"""
        numCalibPulses_int = int(self.triggerNumCalibrationPulsesBox.toPlainText())
        # Ensures proper number of calibration pulses per trigger
        bits = f"{numCalibPulses_int:05b}{auxRegAddress:02b}".zfill(16)
        bitsSplit = [bits[i:i+8] for i in range(0,len(bits),8)][::-1]
        bits = "".join(bitsSplit)
        # bits = "0000101000001010"
        self.status.send(self) # Reset for rising edge
        self.status.sendFifoAOperation(self,fifoOperation,counter=2,address=6)
        serialResult = serialMod.writeToChip(self,'A',bits)
        if reset:
            self.status.send(self)
        return serialResult

    def selectI2CinterfaceAndCalPulses(self,fifoOperation=1,auxRegAddress=None,reset=False):
        """The current I2C interface and the number of calibration pulses per trigger are stored in the same
           status register of the FPGA. This combines both operations into one function"""
        numCalibPulses_int = int(self.triggerNumCalibrationPulsesBox.toPlainText())
        if numCalibPulses_int > 31:
            self.showError("Number of calibration pulses setting overflow. Max Value: 31")
            return
        if not auxRegAddress: auxRegAddress = 0

        bits = f"{numCalibPulses_int:05b}{auxRegAddress:02b}".zfill(16)
        bitsSplit = [bits[i:i+8] for i in range(0,len(bits),8)][::-1]
        bits = "".join(bitsSplit)

        self.status.send(self) # Reset for rising edge
        self.status.sendFifoAOperation(self,fifoOperation,counter=2,address=6)
        serialResult = serialMod.writeToChip(self,'A',bits)
        if reset:
            self.status.send(self)
        return serialResult

    def setupConfigurations(self,configDict,cfgFile,tabName):
        """Interprets the mandatory 'Categories' section at the top of the config file."""
        # Setup parsing of the config file
        config = configparser.ConfigParser()
        config.optionxform=str
        config.read(cfgFile)
        # Create a dictionary linking each category name and address
        # e.g. ch1: SlowControl,0
        #     - ch1 is key/name
        #     - SlowControl is template
        #     - 0 is the chip address for R/W operations
        categoryDict = dict(config.items('Categories'))
        # Create a default config dict
        setattr(self,tabName+'defaultConfigurations',{})

        for catName in categoryDict:
            # For each row, get the template and address
            catTemplate,catAddress,*subAddress = categoryDict[catName].split(',')
            # Create Configuration object and give give a reference to ColutaGUI
            cat = CC.Configuration(self,cfgFile,tabName,catTemplate,catName,catAddress,subAddress)
            defaultDict = getattr(self,tabName+'defaultConfigurations')
            defaultDict[catName] = cat.clone()
            configDict[catName] = cat # add to config dictionary
            cat.updateGUIText()

    def updateConfiguration(self,configName,settingName,tabName):
        configurations = getattr(self,tabName+'Configurations')
        setting = configurations[configName].getSetting(settingName) 
        length = setting.length
        previousValue = setting.value
        boxName = setting.box  
        boxType = type(getattr(self,boxName))
        if boxType==QtWidgets.QPlainTextEdit:
            plainText = getattr(self,boxName).toPlainText()
            try: decimal = int(plainText)
            except: decimal = 0
            binary = colutaMod.decimalToBinaryString(decimal,length)
            if len(binary)>length:
                self.showError('Setting overflow! Configuration not changed.')
                try:
                    previousDecimalStr = str(colutaMod.binaryStringToDecimal(previousValue))
                except: 
                    self.showError('Invalid input! Cannot convert to binary')
                getattr(self,boxName).document().setPlainText(previousDecimalStr)
                return
        elif boxType==QtWidgets.QComboBox:
            index = getattr(self,boxName).currentIndex()
            binary = colutaMod.decimalToBinaryString(index,length)
        elif boxType==QtWidgets.QCheckBox:
            binary = '1' if getattr(self,boxName).isChecked() else '0'
        else:
            binary = ''
            print('Could not find setting box {0}.'.format(boxName))
        configurations[configName].setConfiguration(settingName,binary)
        print('Updated {} {},{}:{}'.format(tabName,configName,settingName,binary))

    def sendUpdatedConfigurations(self):
        for chip in self.chips:
            configurations = getattr(self,chip+'Configurations')
            for categoryName in configurations:
                if categoryName[-2:]=='__':
                    continue
                category = configurations[categoryName]
                isI2C = category.address==0
                if category.updated:
                    # if self.debug:
                    print('Updating',chip,categoryName,sep=' ')
                    if 'dac' in categoryName:
                        self.configureDAC()
                        category.updated = False
                    elif category.isI2C:
                        category.sendUpdatedConfiguration(category.isI2C)
                    else:
                        # should send LAUROC configurations
                        if 'lauroc' in chip: print('config lauroc')
                        continue
                        # category.sendUpdatedConfiguration(category.isI2C)

    def connectButtons(self,configDict):
        # Create a signal response for each configuration box
        for configName in configDict: # Loop over list of configuration names
            singleConfigSettings = configDict[configName].settings
            for setting in singleConfigSettings: # Loop over settings
                # Get the box's name and type
                settingName = setting.name
                # Skip filler and read-only bits
                if 'Fill' in settingName or settingName[-2:]=='__': continue
                # Find the UI box corresponding to this setting
                boxName = setting.box
                boxType = type(getattr(self,boxName))
                tab = setting.tab
                # Define a lambda function, "update", to pass arguments to connect signal.
                # Ok, so there have to be two lambdas. The inner lambda is the function that we are
                # passing, while the outer lambda is a meta-function that passes the names to create
                # each unique inner function. See https://stackoverflow.com/questions/4578861.
                update = lambda x,y,z : lambda : self.updateConfiguration(x,y,z)
                # Finally, we call the appropriate method for each type of input box
                if boxType==QtWidgets.QPlainTextEdit:
                    getattr(self,boxName).textChanged.connect(update(configName,setting.name,tab))
                elif boxType==QtWidgets.QComboBox:
                    getattr(self,boxName).currentIndexChanged.connect(update(configName,setting.name,tab))
                elif boxType==QtWidgets.QCheckBox:
                    getattr(self,boxName).stateChanged.connect(update(configName,setting.name,tab))
                elif boxType==QtWidgets.QLabel:
                    pass
                else:
                    print('Could not find setting box {0}.'.format(boxName))

    def copyConfigurations(self,tabName,configName,chips=[],channels=[]):
        """Copy configuration bits from one channel to other channel(s)"""
        configurations = getattr(self,tabName+'Configurations')
        for setting in configurations[configName].settings:
            for chip in chips:
                configurationsTmp = getattr(self,chip+'Configurations')
                for channel in channels:
                    if tabName==chip and configName==channel: continue
                    settingTmp = configurationsTmp[channel].getSetting(setting.name)
                    boxName = settingTmp.box
                    boxType = type(getattr(self,boxName))
                    if boxType==QtWidgets.QPlainTextEdit:
                        decimalString = str(colutaMod.binaryStringToDecimal(setting.value))
                        getattr(self,boxName).document().setPlainText(decimalString)
                    elif boxType==QtWidgets.QComboBox:
                        setIndex = colutaMod.binaryStringToDecimal(setting.value)
                        getattr(self,boxName).setCurrentIndex(setIndex)
                    elif boxType==QtWidgets.QCheckBox:
                        if setting.value=='1': getattr(self,boxName).setChecked(True)
                        elif setting.value=='0': getattr(self,boxName).setChecked(False)
                        else: self.showError('CHIPCONFIGURATION: Error updating GUI. {}'.format(boxName))
                    elif boxType==QtWidgets.QLabel:
                        pass
                    else:
                        print('Could not find setting box {0}.'.format(boxName))

    def checkControl(self,tabName,configName,settingName=None):
        """Check configuration bits of a specific setting"""
        configurations = getattr(self,tabName+'Configurations')
        category = configurations[configName]
        if category.isI2C:
            fromBoard = colutaMod.i2cReadBack(self,tabName,configName,i2cAddress=category.i2cAddress)
        else:
            fromBoard = self.fifoAReadControl(tabName,configName)
        if settingName is None:
            lastKnown = category.bits
            print(lastKnown)
            return fromBoard==lastKnown
        else:
            setting = category.getSetting(self,settingName)
            sPos = setting.position
            sLen = setting.length
            cBits = category.bits
            settingFromBoard = fromBoard[-sPos-sLen:-sPos]
            if sPos==0:
                settingFromBoard = fromBoard[-sLen:]
            return settingFromBoard==setting.value

    def configureLpGBT(self):
        """Initial configuration of the LpGBT registers"""
        print('Configuring LpGBT')
        self.LpGBTControl(lpgbtRstb='1',linkResetPulse='0')
        time.sleep(0.1)
        self.LpGBTControl(lpgbtRstb='0',linkResetPulse='0')
        time.sleep(0.1)
        self.LpGBTControl(lpgbtRstb='1',linkResetPulse='0')
        # serialResult = colutaMod.i2cWrite(self,'lpgbt','psdllconfig')
        for catName in self.lpgbtConfigurations:
           # print(catName, '{0:03x}'.format(self.lpgbtConfigurations[catName].address),
           #      '{0:02x}'.format(int(str(self.lpgbtConfigurations[catName].bits),2)))
            colutaMod.i2cWrite(self, 'lpgbt', catName)
            # self.readLpGBT(catName)
        time.sleep(2)
        self.LpGBTControl(linkResetPulse='1')

    def readLpGBT(self,category):
        """Read back LpGBT configuration bits"""
        print('Reading LpGBT config bits')
        serialResult = colutaMod.i2cRead(self,'lpgbt',category)
        # serialResult = colutaMod.i2cRead(self,'lpgbt','clkgconfig0')

    def configureLAUROC2(self):
        self.configureLAUROC(resetBFlag='0')
        self.configureLAUROC(resetBFlag='1')

    def configureLAUROCinit(self):
     #   self.configureLAUROC('slowcontrol',resetBFlag='1',selectFlag='1',bits='0'*276)
        #time.sleep(2)
        self.configureLAUROC('slowcontrol',resetBFlag='0',selectFlag='1',bits='0'*276)  
        self.configureLAUROC('slowcontrol',resetBFlag='0',selectFlag='1',bits='0'*276)
        # self.configureLAUROC('lauroc1','proberegister',resetBFlag='0',selectFlag='0',bits='0'*50)
        # self.configureLAUROC('lauroc1','proberegister',resetBFlag='0',selectFlag='0',bits='0'*50)  

    def configureLAUROC(self,categoryName,resetBFlag='1',selectFlag='1',bits=None):
        """
        Temp? function to configure LAUROC chips
        Both LAUROC chips are configured at once, so 
        need to write a new function to send updated configs 
        for the LAUROC chips
        """
        if self.debug: print('Configuring LAUROC')
        #categoryName = 'slowcontrol'
        chip = 'lauroc1'
        configurations1 = getattr(self,'lauroc1'+'Configurations')
        configurations2 = getattr(self,'lauroc2'+'Configurations')
        category1 = configurations1[categoryName]
        category2 = configurations2[categoryName]
        address = category1.address
        # resetBFlag = '0'
        # selectFlag = '1' # For slow control bits, flag is '1'. For probe register bits, flag is '0'
        # bits = 6*'0010' # Temp bits from top_tb.v
        # No need to send bit 139
        if categoryName == 'slowcontrol':
            laurocDataBits1 = category1.bits.zfill(138)
            laurocDataBits2 = category2.bits.zfill(138)
        elif categoryName == 'proberegister':
            laurocDataBits1 = category1.bits
            laurocDataBits2 = category2.bits

        # laurocDataBits2 = '1'.zfill(138)
        # bits = (laurocDataBits+laurocDataBits+selectFlag+resetBFlag).zfill(280)
        # bits = ('1'+'0'*136+'1'+'1'+'0'*136+'1'+selectFlag+resetBFlag).zfill(280)
        # bits = ('10'*138+selectFlag+resetBFlag).zfill(280)
        if bits is not None:
            bits = (bits + selectFlag + resetBFlag).zfill(280)
        else:
            # print(type(resetBFlag),type(selectFlag),type(bits))
            bits = (laurocDataBits1+laurocDataBits2+selectFlag+resetBFlag).zfill(280)
            # bits = ('0'*138+'1'+'0'*136+'1'+selectFlag+resetBFlag).zfill(280) 
        if self.debug: print(bits)
        bitsSplit = [bits[i:i+8] for i in range(0,len(bits),8)][::-1]
        bits = "".join(bitsSplit)
        nBits = len(bits)
        nByte = int(nBits/8)
        self.status.sendFifoAOperation(self,1,nByte,address)
        serialResult = serialMod.writeToChip(self,'A',bits)
        self.status.sendStartControlOperation(self,1,address)
        self.status.send(self)

    def configureColuta(self,chip):
        print('Configuring {}'.format(chip.upper()))
        # self.selectI2Cinterface(fifoOperation=1,auxRegAddress=1)
        configurations = getattr(self,chip+'Configurations')
        for categoryName in configurations:
            if categoryName[-2:]=='__':
                continue
            category = configurations[categoryName]
            if self.debug:
                print('Updating',chip,categoryName,sep=' ')
                category.sendUpdatedConfiguration(category.isI2C)

        self.status.send(self)
        # print('--- Readback ---')
        # self.checkControl(chip,'ch1')
    
    def bunchcrossingControl(self):
        bcrstEnable = '1'
        bcrstPeriod = '1000110011000'
        dataBits = (bcrstPeriod+bcrstEnable).zfill(64)
        dataBitsSplit = [dataBits[i:i+8] for i in range(0,len(dataBits),8)][::-1]
        dataBitsToSend = "".join(dataBitsSplit)
        
        self.status.sendFifoAOperation(self,operation=1,counter=2,address=5)
        serialMod.writeToChip(self,'A',dataBitsToSend)
        self.status.sendStartControlOperation(self,operation=1,address=5)


    def LpGBTControl(self,linkResetPulse='0',lpgbtRstb='1',lpgbtMode='1001'):
    # def LpGBTControl(self,linkResetPulse='0',lpgbtRstb='1',lpgbtMode='1011'):
        """Startup commands to configure the LpGBT control register"""
        #linkResetPulse = '0'
        reservedBit = '0'
        downlinkECField = '11'
        downlinkICField = '11'
        downlinkSkipCycle = '00'
        #lpgbtRstb = '0' # Bit 0 means no reset.
        lpgbtPORDIS = '0'
        # lpgbtMode = '1011' # 10 Gbps, FEC5, transceiver mode
        # lpgbtMode = '1001' # 10 Gbps, FEC5, simple tx mode
        lpgbtStateovrd = '0'
        lpgbtLockmode = '0'
        lpgbtSCI2C = '1'
        bitsZero = '0'*7
        downlinkUserData = '1'.zfill(32)
        lpgbtControlBits = downlinkUserData+\
                         bitsZero+\
                         lpgbtSCI2C+\
                         lpgbtLockmode+\
                         lpgbtStateovrd+\
                         lpgbtMode+\
                         lpgbtPORDIS+\
                         lpgbtRstb+\
                         downlinkSkipCycle+\
                         downlinkICField+\
                         downlinkECField+\
                         reservedBit+\
                         linkResetPulse
        dataBitsToSend = lpgbtControlBits.zfill(64)
        # dataBitsToSend = "1000000010010110000111100".zfill(64)
        dataBitsSplit = [dataBitsToSend[i:i+8] for i in range(0,len(dataBitsToSend),8)][::-1]
        dataBitsToSend = "".join(dataBitsSplit)
        self.status.send(self)
        self.status.sendFifoAOperation(self,operation=1,counter=7,address=1)
        serialMod.writeToChip(self,'A',dataBitsToSend)
        self.status.sendStartControlOperation(self,operation=1,address=1)
        self.status.send(self)

    def configureDAC(self,startup=False,reset=False):
        if self.debug:
            print('Configuring DAC')

        if self.controlSPIInstructionBox.textChanged:
            SPIInstruction_int = int(self.controlSPIInstructionBox.toPlainText())
            SPIInstruction = '{:024b}'.format(SPIInstruction_int)
            if len(SPIInstruction) < 24:
                self.showError('DAC: SPI Instruction value must be 24 bits')
                return
            if len(SPIInstruction) > 24:
                self.showError('DAC: SPI Instruction value cannot exceed 24 bits')
                return

        if self.controlLDACControlBox.textChanged:
            LDACControl = self.controlLDACControlBox.toPlainText()
            if len(LDACControl) > 3:
                self.showError('DAC: LDAC control value cannot exceed 3 bits')
                return

        if reset: SPIInstruction = '0'*24

        dataBitsToSend = (LDACControl+SPIInstruction).zfill(32)
        
        # SPIChain    = '000000000000000000000000000000000000000100'
        # SPIRegister = '000000001000000010000000'
        # dataBitsToSend = SPIChain+SPIRegister

        dataBitsSplit = [dataBitsToSend[i:i+8] for i in range(0,len(dataBitsToSend),8)][::-1]
        dataBitsToSend = "".join(dataBitsSplit)
        self.status.sendFifoAOperation(self,operation=1,counter=4,address=2)
        serialMod.writeToChip(self,'A',dataBitsToSend)
        self.status.sendStartControlOperation(self,operation=1,address=2)
        # self.status.sendCalibrationPulse(self)
        self.status.send(self)
        if startup: 
            # puts a reasonable pulse height in the text box after startup is done
            self.controlSPIInstructionBox.document().setPlainText('256')

    def selectCalibrationPulses(self):
        """Select the number of calibration pulse per trigger"""

        auxRegAddress = self.triggerAuxiliaryRegisterAddressBox.toPlainText()
        numCalibPulses_int = int(self.triggerNumCalibrationPulsesBox.toPlainText())
        numCalibPulses = '{:05b}'.format(numCalibPulses_int)
        if auxRegAddress is '':
            self.showError("TRIGGER: Invalid auxiliary register value")
            return

        if len(auxRegAddress)>2:
            self.showError("Setting overflow. Max length: 2 bits")
            return

        if len(numCalibPulses)>5:
            self.showError("Setting overflow. Max length: 5 bits")
            return

        if self.debug:
            print("Selecting {} calibration pulses per trigger".format(int(numCalibPulses,2)))

        dataBitsToSend = (numCalibPulses+auxRegAddress).zfill(16)
        dataBitsSplit = [dataBitsToSend[i:i+8] for i in range(0,len(dataBitsToSend),8)][::-1]
        dataBitsToSend = "".join(dataBitsSplit)

        self.status.send(self) # Reset for rising edge
        self.status.sendFifoAOperation(self,1,counter=2,address=6)
        serialMod.writeToChip(self,'A',dataBitsToSend)

    def sendPulseTakeSamples(self):
        '''Sends calibration pulse and take samples'''
        self.awgFreq = 320
        self.pulseLength = 440 
        self.runType = 'onboard'
        self.status.sendCalibrationPulse(self)
        self.takeSamples()

    def updateNSamplesBurstMode(self):
        """Update nSamples box with instrument control LAr pulse variables"""
        try:
            self.nSamples = int(self.n_samples_per_pulseBox.toPlainText())*int(self.n_pulsesBox.toPlainText())
            if self.nSamples==self.dualPortBufferDepth+1:
                self.nSamples = 2047.5
            elif self.nSamples > self.dualPortBufferDepth+2:
                self.showError('ERROR: Exceeded maximum number of samples. Max value: 4096.')
                self.nSamples = 2047.5
        except Exception:
            self.nSamples = 0

    def sendAFGPulseTakeSamples(self):
        # self.updateNSamplesBurstMode()
        if self.pOptions.instruments:
            self.awgFreq = 1200
            self.pulseLength = 64
            self.runType = 'pulse'
            self.function_generator.sendTriggeredPulse()
            self.takeSamples()
        else:
            self.showError('ERROR: No external AWG found')
            return

    def sendExternalTrigger(self):
        self.status.send(self)
        self.status.updatePulseDelay(self)
        self.status.send(self)

    def configureLAUROCDynamicRange(self):
        """Set the default dynamic range values for the two LAUROC chips"""
        # get the index of the dynamic range value
        dynamicRangeIdx = self.controlLAUROCDynamicRangeBox.currentIndex()

        # Get the slow control configurations
        slowControlConfigs = self.lauroc1Configurations['slowcontrol']

        # Create new dicts for the three dynamic range settings
        dynamicRange_2mA = dict([('biasPaSWR0255mA','0'),
                            ('biasPaSWR02510mA','0'),
                            ('ch4Rf','1010'),
                            ('ch1C2','001011010'),
                            ('ch2C2','001011010'),
                            ('ch3C2','001011010'),
                            ('ch4C2','001011010')])

        dynamicRange_5mA = dict([('biasPaSWR0255mA','1'),
                            ('biasPaSWR02510mA','0'),
                            ('ch1C2','001100100'),
                            ('ch2C2','001100100'),
                            ('ch3C2','001100100')])

        dynamicRange_10mA = dict([('biasPaSWR0255mA','0'),
                             ('biasPaSWR02510mA','1'),
                             ('ch4Rf','0010'),
                             ('ch1C2','011011100'),
                             ('ch2C2','011011100'),
                             ('ch3C2','011011100'),
                             ('ch4C2','011011100')])

        # Get the default configurations (ones read from the config file)
        defaultDict = self.lauroc1defaultConfigurations['slowcontrol']

        # Create a list of (setting,value) pairs 
        defaultSettings = [(setting.name,setting.value) for setting in defaultDict.settings]        
        
        # 2mA dynamic range settings
        if dynamicRangeIdx == 0:
            for (settingName, settingValue) in defaultSettings:
                # We need to keep default settings for the values not listed
                # in the dynamic range dicts. Thus, the try-except block will
                # keep the use the default values for the settings not listed  
                # in the dynamic range dicts
                try:
                    newSettingValue = dynamicRange_2mA[settingName]
                except:
                    newSettingValue = settingValue
                slowControlConfigs.setConfiguration(settingName, newSettingValue)

        # 5mA dynamic range settings
        elif dynamicRangeIdx == 1:
            for (settingName, settingValue) in defaultSettings:
                try:
                    newSettingValue = dynamicRange_5mA[settingName]
                except:
                    newSettingValue = settingValue
                slowControlConfigs.setConfiguration(settingName, newSettingValue)

        # 10mA dynamic range settings
        elif dynamicRangeIdx == 2:
            for (settingName, settingValue) in defaultSettings:
                try:
                    newSettingValue = dynamicRange_10mA[settingName]
                except:
                    newSettingValue = settingValue
                slowControlConfigs.setConfiguration(settingName, newSettingValue)

        # Update the GUI boxes
        slowControlConfigs.updateGUIText()
        # Copy the configurations to LAUROC2 slow control
        self.copyConfigurations('lauroc1','slowcontrol',chips=['lauroc2'],channels=['slowcontrol'])
        # Configure LAUROC slow control
        self.configureLAUROC('slowcontrol')

    def configureAll(self):
        print('Setting dynamic range and configuring LAUROCs')
        self.configureLAUROCDynamicRange()
        self.configureLAUROC('slowcontrol')
        self.configureLAUROC('proberegister',selectFlag='0')
        print('Configuring lpGBT and COLUTAs')
        self.sendUpdatedConfigurations()
        print('Configuring onboard pulser')
        self.configureDAC()
        # self.selectCalibrationPulses() ### TODO: why does the GUI not work when I comment this out? 
        if self.pOptions.instruments:
            print('Initializing instrumentation and applying physics pulses')
            instrumentControlMod.initializeInstrumentation(self)
            self.function_generator.applyPhysicsPulse()
            self.function_generator.trigger()
        print('Done configuring all chips and instruments')
