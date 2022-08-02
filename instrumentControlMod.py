"""
Module for instrument control 

name: instrumentControl.py
author: D.Panchal
email: dpanchal@utexas.edu
date: October 18, 2018
"""

# pyVISA library to set up connection with the instruments
try:
    import visa
except:
    pass
import numpy
from PyQt5 import QtWidgets
import configparser
import time,os
import colutaMod
from itertools import product

class InstrumentControl():

    def __init__(self,coluta,configFile):
        """
        Initialize the variables needed for instrument control
        """
        self.coluta = coluta

        # self.resourceManager = visa.ResourceManager('@py')
        self.resourceManager = visa.ResourceManager()
        self.devices = {}
        self.configFile = configFile
        self.setupDeviceConfiguration()

    def setupDeviceConfiguration(self):
        config = configparser.ConfigParser()
        config.optionxform=str

        if not os.path.isfile(self.configFile):
            self.coluta.showError('INSTRUMENT CONTROL: Configuration file found')

        config.read(self.configFile)
        if not config.sections():
            self.coluta.showError('INSTRUMENT CONTROL: Configuration file has no sections')

        config.read(self.configFile)
        devices = dict(config.items('Devices'))

        self.frequencies = dict(config.items('Frequencies'))

        for deviceType,deviceName in devices.items():
            if not config.has_section(deviceType):
                self.coluta.showError('INSTRUMENT CONTROL: No settings found for the device: {0}'.format(deviceType))
                continue

            configItems = config.items(deviceType)
            deviceInstance = globals()[deviceName](self.coluta,self.resourceManager,configItems)
            setattr(self,deviceType,deviceInstance)
            #setattr(self,deviceName,Device(self.coluta,self.resourceManager,configItems))
            self.updateGUIText(self.coluta,getattr(self,deviceType))


    def updateGUIText(self,coluta,device):
        # print(hasattr(devic)
        for setting,value in getattr(device,'settings').items():
            settingName = setting
            boxName = settingName+'Box'
            boxType = type(getattr(coluta,boxName))
            if boxType == QtWidgets.QPlainTextEdit:
                configuration = str(value)
                getattr(coluta,boxName).document().setPlainText(configuration)
            elif boxType == QtWidgets.QComboBox:
                # setIndex = colutaMod.binaryStringToDecimal(value)
                # getattr(coluta,boxName).SetCurrentIndex(setIndex)
                value = int(value)
                getattr(coluta,boxName).setCurrentIndex(value)
            elif boxType == QtWidgets.QCheckBox:
                if value == '1': 
                    getattr(coluta,boxName).SetChecked(True)
                elif value == '0': 
                    getattr(coluta,boxName).SetChecked(False)
                else: 
                    coluta.showError('INSTRUMENT CONTROL: Error updating GUI')
            elif boxType == QtWidgets.QLabel:
                pass
            else:
                print('Could not find setting box {0}'.format(boxName))

    def getCurrentConfig(self,device):
        txt = getattr(self,device).getCurrentConfig()
        getattr(self.coluta,'textDisplayBox').document().setPlainText(txt)

class Setting:
    def __init__(self,configItems):
        self.names = []
        self.values = []

        for item in configItems:
            self.names.append(item[0])
            v = item[1].split(',')
            #v = item[1]
            #self.values.append(v)
            if len(v) == 1:
                self.values.append(v[0])
            else:
                self.values.append(v)

        self.updated = True
        self.settings = dict(zip(self.names,self.values))

    def getSetting(self,settingName):
        try:
            value = self.settings[settingName]
        except KeyError:
            print('Key Error: The device does not have the setting ' +settingName)

        return value

    def setSetting(self,settingName,settingValue):
        try:
            #print(settingValue)
            self.settings[settingName] = settingValue
            self.updated = True
        except KeyError:
            print('Cannot update setting')

class Device(Setting):
    def __init__(self,coluta,resourceManager,configItems):
        Setting.__init__(self,configItems)
        self.resourceManager = resourceManager
        self.coluta = coluta
        # self.device = self.connect()

    def connect(self):
        ipAddress = self.getSetting('ipAddress')
        print(ipAddress)
        try:
            device = self.resourceManager.open_resource("TCPIP::"+ipAddress)
            print(device.query("*IDN?"))
        except visa.VisaIOError:
            self.coluta.showError('INSTRUMENT CONTROL: Cannot connect to IP address: {0}'.format(ipAddress))
        return device
    def disconnect(self):
        try:
            self.device.query("*IDN?")
            self.device.close()
        except visa.VisaIOError:
            self.coluta.showError('INSTRUMENT CONTROL: Device is already closed')

    def clearStatus(self,device):
        self.device.write("*CLS")

    def updateSetting(self,settingName):
        try:
            boxName = settingName+'Box'
            value = getattr(self.coluta,boxName).document().toPlainText()
            #print('value: ',value)
            self.setSetting(settingName,value)
        except KeyError:
            self.coluta.showError('INSTRUMENT CONTROL: Invalid setting to update')

    def updateDataSetting(self,runType,settingName):
        '''Updates the IC setting as well as the data parser setting'''
        try:
            boxName = settingName+'Box'
            boxType = type(getattr(self.coluta,boxName))
            if boxType == QtWidgets.QPlainTextEdit:
                value = getattr(self.coluta,boxName).document().toPlainText()
                self.setSetting(settingName,value)
                getattr(self.coluta.ODP,runType+'Run').settings[settingName] = value
            elif boxType == QtWidgets.QComboBox:
                valueIndex = str(getattr(self.coluta,boxName).currentIndex())
                self.setSetting(settingName,valueIndex)
                value = self.coluta.IC.frequencies[valueIndex]
                if value == 'Other':
                    value = getattr(self.coluta,boxName+'_2').document().toPlainText()
                getattr(self.coluta.ODP,runType+'Run').settings[settingName] = value
        except KeyError:
            self.coluta.showError('INSTRUMENT CONTROL: Invalid setting to update')

    def trigger(self):
        raise NotImplementedError

class keithley3321A(Device):
    def __init__(self,coluta,resourceManager,configItems):
        self.coluta = coluta
        Device.__init__(self,coluta,resourceManager,configItems)
        self.device = self.connect()
        self.voltageUnit = self.getSetting('voltageUnit')

    def applySin(self,address,channel):

        frequency = self.getSetting('signalFrequency').split(',')
        amplitude = self.getSetting('amplitude').split(',')
        #print(amplitude)
        #for amp,freq in zip(amplitude,frequency):
        for freq in frequency:
            for amp in amplitude:
                self.device.write("APPL:SIN "+str(freq)+"MHZ, "+str(amp)+"V")
                time.sleep(1)
                if self.coluta.pOptions.debug:
                    print('INSTRUMENT -> Frequency: {0}, Amplitude: {1}'.format(freq,amp))
                # print(amp,freq)
                # self.coluta.taEkeSamples(address,channel,voltage=amp,frequency=freq)
                self.coluta.takeDual(voltage=amp+' '+self.voltageUnit,frequency=freq+' MHz')
                time.sleep(1)

    def setVoltageUnitRMS(self):
        self.device.write("VOLT:UNIT Vrms")

    def getCurrentConfig(self):
        return self.device.query("APPL?")

    def getCurrentVolt(self):
        return float(self.device.query("VOLT?"))

    def getCurrentFreq(self):
        return float(self.device.query("FREQ?"))

    def setVoltageUnit(self):
        unit = getattr(self.coluta,'voltageUnitBox').document().toPlainText()
        self.voltageUnit = unit
        self.setSetting('voltageUnit',unit)
        self.device.write("VOLT:UNIT "+unit)

class t3awg3252(Device):
    def __init__(self,coluta,resourceManager,configItems):
        self.coluta = coluta
        Device.__init__(self,coluta,resourceManager,configItems)
        self.device = self.connect()
        self.voltageUnit = self.getSetting('voltageUnit')
        self.setReferenceClock()

    def setReferenceClock(self):
        self.device.write("SOURce:ROSCillator:SOURce EXTernal")
        self.device.write("SOURce:ROSCillator:FREQuency 10MHZ")

    def applySin(self):
        self.coluta.runType = 'sine'
        freq = self.coluta.IC.frequencies[self.getSetting('sine_frequency')]
        amplitude = self.getSetting('sine_amplitude').split(',')

        self.device.write("*RST")
        for amp in amplitude:
            self.device.write("SOURce1:FUNCtion:SHAPe SINusoid")
            self.device.write("SOURce1:FREQuency "+str(freq)+"MHZ")
            self.device.write("SOURce1:VOLTage "+str(amp))
            self.device.write("OUTPut1:STATe ON")
            self.device.write("AFGControl:START")

    def applyRamp(self):
        self.coluta.runType = 'ramp'
        frequency = self.getSetting('ramp_frequency').split(',')
        amplitude = self.getSetting('ramp_amplitude').split(',')

        self.device.write("*RST")
        for freq,amp in product(frequency,amplitude):
            self.device.write("SOURce1:FUNCtion:SHAPe RAMP")
            self.device.write("SOURce1:FREQuency "+str(freq)+"MHZ")
            self.device.write("SOURce1:VOLTage "+str(amp))
            self.device.write("OUTPut1:STATe ON")
            self.device.write("AFGControl:START")

    def applyPedestal(self):
        self.coluta.runType = 'pedestal'
        self.device.write("*RST")
        self.device.write("AFGControl:STOP")

    def applyPulse(self):
        self.coluta.runType = 'pulse'
        CH1_Frequency = 0.6253257
        CH1_Amplitude = self.getSetting('pulse_amplitude')
        try:
            from physics_pulse import byteSamples
        except:
            self.coluta.showError('Unable to find physics_pulse.py')
            return
        self.device.write_binary_values('TRACE1:DATA ', byteSamples, datatype='B', is_big_endian=False)
        self.device.write("SOURce1:FUNCtion:SHAPe ARBB")
        self.device.write("SOURce1:VOLTage:AMPLitude " + str(CH1_Amplitude))
        self.device.write("SOURce1:FREQuency " + str(CH1_Frequency) + "MHZ")
        self.device.write("OUTPut1:STATe ON")
        self.device.write("AFGControl:START")

    def applyBurstPulse(self):
        """Send multiple pulses"""
        self.coluta.runType = 'pulse'
        CH1_Frequency = 0.1
        CH1_Amplitude = self.getSetting('pulse_amplitude').split(',')
        #N_Pulses = self.getSetting('n_pulses')
        N_Pulses = str(self.coluta.n_pulsesBox.toPlainText())
        N_Samples = self.getSetting('n_samples_per_pulse').split(',')
        try:
            from physics_pulse import byteSamples
        except:
            self.coluta.showError('Unable to find physics_pulse.py')
            return
        bursts = "AFGControl:BURST " + N_Pulses
        self.device.write(bursts)
        self.device.write("AFGControl:RMODe BURSt")
        self.device.write_binary_values('TRACE1:DATA ', byteSamples, datatype='B', is_big_endian=False)
        self.device.write("SOURce1:FUNCtion:SHAPe ARBB")
        self.device.write("SOURce1:VOLTage:AMPLitude " + str(CH1_Amplitude))
        self.device.write("SOURce1:FREQuency " + str(CH1_Frequency) + "MHZ")
        self.device.write("OUTPut1:STATe ON")
        self.device.write("AFGControl:START")

    def applyPhysicsPulse(self):
        self.coluta.runType = 'pulse'
        # CH1_Frequency = 0.078288
        # CH1_Frequency = 0.083507
        # CH1_Frequency = 1.251303
        CH1_Frequency = 0.6253257
        # CH1_Frequency = self.getSetting('ramp_frequency')
        #CH1_Amplitude = self.getSetting('pulse_amplitude')
        CH1_Amplitude = str(self.coluta.pulse_amplitudeBox.toPlainText())
        N_Pulses = str(self.coluta.n_pulsesBox.toPlainText())
        try:
            from physics_pulse import byteSamples2
        except:
            self.coluta.showError('Unable to find physics_pulse.py')
            return
        # bursts = "AFGControl:BURST " + N_Pulses
        # self.device.write("*RST")
        # self.device.write(bursts)
        # self.device.write("AFGControl:RMODe BURSt")

        self.device.write_binary_values('TRACE1:DATA ', byteSamples2, datatype='B', is_big_endian=False)
        self.device.write("SOURce1:BURSt:STATe ON")
        self.device.write("SOURce1:BURSt:MODE TRIGgered")
        self.device.write("SOURCE1:BURSt:NCYCles " + N_Pulses)
        # self.device.write("SOURCE1:BURSt:NCYCles 1")
        self.device.write("SOURce1:FUNCtion:SHAPe ARBB")
        # self.device.write("SOURce1:VOLTage:AMPLitude " + str(CH1_Amplitude))
        self.device.write("SOURce1:VOLTage:HIGH 0")
        self.device.write("SOURce1:VOLTage:LOW " + str(-1*float(CH1_Amplitude)))
        self.device.write("SOURce1:FREQuency " + str(CH1_Frequency) + "MHZ")
        self.device.write("OUTPut1:STATe ON")
        # self.device.write("AFGControl:COPY 1")
        self.device.write("AFGControl:START")


    def trigger(self):
        """Selects the external trigger for the AWG"""
       # triggerSource = self.coluta.triggerSourceBox.getCurrentText()
        #triggerSource = triggerSource.upper()[:3]

        triggerThresholdUnit = self.coluta.triggerVoltageBox.currentIndex()
        if triggerThresholdUnit == 0:
            triggerThresholdUnit = 'mV'
        elif triggerThresholdUnit == 1:
            triggerThresholdUnit = 'V'
        
        triggerSlope = self.coluta.triggerSlopeBox.currentIndex()
        if triggerSlope == 0:
            triggerSlope = 'FALLING'
        elif triggerSlope == 1:
            triggerSlope = 'RISING'

        triggerThreshold = str(self.coluta.triggerThresholdBox.toPlainText())

        # Reset the trigger
        self.device.write("TRIGger:ABORt")
        # Select the source, slope
        self.device.write("TRIGger:SOURce EXTernal")
        self.device.write("TRIGger:SLOPe {}".format(triggerSlope))
        # Set the threshold voltage level and the impedance
        self.device.write("TRIGger:THREshold {} {}".format(triggerThreshold,triggerThresholdUnit))
        self.device.write("TRIGger:IMPedance 50Ohm")
        self.device.write("TRIGger1:OUTPut:STATe ON")
        #print(self.device.write("TRIGger:IMPedance?"))

    def sendTriggeredPulse(self):
        if self.coluta.runType == 'pulse':
            # It's still possible the user messed with the AWG parameters
            print('Waveform already loaded')
        else:
            print('Loading waveform')
            #self.applyBurstPulse()
            #self.device.write("ABORt")
            self.applyPhysicsPulse()
        print('Sending trigger')
        #self.device.write("*TRG")
        self.coluta.sendExternalTrigger()

def initializeInstrumentation(coluta):
    '''Import libraries and define relevant attributes for testBoardGUI.'''
    # Try to import VISA. If it fails, show warning and exit.
    try:
        import visa
    except:
        coluta.showError('INSTRUMENT: VISA not available. Unable to initialize.')
        return

    # Setup instance of InstrumentControl class
    coluta.IC = InstrumentControl(coluta,'./config/instrumentConfig.cfg')
    coluta.function_generator = coluta.IC.function_generator
    coluta.pOptions.instruments = True

    # define the buttons on the Instrumentation tab
    coluta.ipAddressBox.textChanged.connect(lambda:updateIpAddress(coluta,'function_generator'))
    coluta.connectInstrumentButton.clicked.connect(lambda:coluta.function_generator.connect())
    coluta.applySineButton.clicked.connect(lambda:coluta.function_generator.applySin())
    coluta.applyRampButton.clicked.connect(lambda:coluta.function_generator.applyRamp())
    coluta.applyPedestalButton.clicked.connect(lambda:coluta.function_generator.applyPedestal())
    coluta.applyPulseButton.clicked.connect(lambda:coluta.function_generator.applyPulse())
    coluta.applyPhysicsPulseButton.clicked.connect(lambda:coluta.function_generator.applyPhysicsPulse())
    # coluta.takeSamplesColutaButton_2.clicked.connect(lambda:coluta.function_generator.applySin(6,'coluta'))
    # coluta.takeSamplesAD9650Button_2.clicked.connect(lambda:coluta.function_generator.applySin(1,'ad9650'))
    updDataSetting = lambda x,y : lambda : coluta.function_generator.updateDataSetting(x,y)
    # coluta.sine_frequencyBox.textChanged.connect(updDataSetting('sine','sine_frequency'))
    coluta.sine_frequencyBox.currentIndexChanged.connect(updDataSetting('sine','sine_frequency'))
    coluta.sine_amplitudeBox.textChanged.connect(updDataSetting('sine','sine_amplitude'))
    coluta.ramp_frequencyBox.textChanged.connect(updDataSetting('ramp','ramp_frequency'))
    coluta.ramp_amplitudeBox.textChanged.connect(updDataSetting('ramp','ramp_amplitude'))
    coluta.pulse_amplitudeBox.textChanged.connect(updDataSetting('pulse','pulse_amplitude'))
    coluta.n_samples_per_pulseBox.textChanged.connect(updDataSetting('pulse','n_samples_per_pulse'))
    coluta.n_pulsesBox.textChanged.connect(updDataSetting('pulse','n_pulses'))
    coluta.n_pulse_timestepBox.textChanged.connect(updDataSetting('pulse','n_pulse_timestep'))
    coluta.offsetBox.textChanged.connect(lambda:coluta.function_generator.updateSetting('offset'))
    
    coluta.instrumentConfigureTriggerButton.clicked.connect(coluta.function_generator.trigger)
    coluta.sendPulseAndTriggerButton.clicked.connect(coluta.function_generator.sendTriggeredPulse)

    # coluta.getCurrentConfigButton.clicked.connect(lambda:coluta.IC.getCurrentConfig('function_generator'))
    # coluta.setVoltageUnitButton.clicked.connect(lambda:coluta.function_generator.setVoltageUnit())

def updateIpAddress(coluta,device):
    oldIPaddress = getattr(coluta.IC,device).getSetting('ipAddress')
    try:
        newIPaddress = coluta.ipAddressBox.toPlainText()
    except Exception:
        # coluta.IC.ipAddress = '10.44.45.58'
        newIPaddress = oldIPaddress
    print('New IP address: ' + newIPaddress)
    getattr(coluta.IC,device).setSetting('ipAddress',newIPaddress)
