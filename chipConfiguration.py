"""Module to store methods related to configuring the COLUTA65 V2 chip

name: chipConfiguration.py
author: C. D. Burton
email: burton@utexas.edu
date: 10 August 2018"""

import os,copy
import configparser
from PyQt5 import QtWidgets
import colutaMod
# from PyQt5.QtCore import QThread,QMutex
# import Thread

class Configuration:
    """Handles, holds, and manipulates configuration bits and settings.
    
    Attributes:
        fileName: The name of the .cfg file containing the initial settings.
        sectionName: Bracketed section in the .cfg whence this object is set.
        bits(str): Full string of configuration bits, from MSB to LSB.
        settings(list<Setting>): List of Settings objects, in the order that they 
                                 will be sent to the chip.
        names(list<str>): List of the setting names. Static once defined in init.
    
    These objects can be set in two ways:
        1) Reading from a config file, during initialization (when the GUI 
           starts up) or upon button press
        2) Setting an individual setting with the setConfiguration function
    A specific setting can be read by calling the getConfiguration() function.
    The writeCfg() method generates a new .cfg file with proper syntax.

    """
    def __init__(self,coluta,fileName,tabName,sectionName,channelName,channelAddress,i2c=''):
        """Initializes the Configuration object.
        
        At first, always read from a .cfg file. Then, once the object has been 
        created, it can be updated with other functions."""
        self.fileName = fileName
        self.tabName = tabName # "coluta1"
        self.sectionName = sectionName # "template"
        self.channelName = channelName # "category"
        self.address = int(channelAddress)
        self.coluta = coluta

        if len(i2c) is not 0 and self.tabName[:-1]!='lauroc': # unpack I2C
            self.isI2C = True
            self.i2cAddress = int(i2c[0])
            if len(i2c) > 1: self.adc = i2c[1]
        else:
            self.isI2C = False
        self.readCfgFile()
        self.updated = True

    def __eq__(self,other):
        for thisSetting,otherSetting in zip(self.settings,other.settings):
            if thisSetting!=otherSetting: return False
        return True

    def __ne__(self, other):
        return not self.__eq__(other)

    def clone(self):
        return self.__deepcopy__()

    def __deepcopy__(self):
        """
        Class implementation of deepcopy
        Reference: https://stackoverflow.com/questions/6279305/typeerror-cannot-deepcopy-this-pattern-object
        """
        return Configuration(self.coluta,self.fileName,self.tabName,self.sectionName,self.channelName,self.isI2C)

    def getSetting(self,name):
        """Searches for setting based on name. Returns if found."""
        for aSetting in self.settings:
            if aSetting.name == name: return aSetting
        self.coluta.showError('Configuration setting '+name+' requested, but not found.')
        return ''

    def setConfiguration(self,name,value):
        """Sets a specific setting value in the list. Regenerates bits attribute."""
        for setting in self.settings:
            if setting.name==name:
                setting.value = value
                break
        self.updateConfigurationBits()
        
    def getConfiguration(self,name):
        """Returns the value of given named setting."""
        for aSetting in self.settings:
            if aSetting.name == name:
                return aSetting.value
        self.coluta.showError('Configuration setting '+name+' requested, but not found.')
        return ''

    def updateConfigurationBits(self,fileName=''):
        """Updates the bits attribute."""

        if self.settings is None:
            if fileName=='':
                self.coluta.showError('No configuration settings loaded and no file specified.')
            else:
                self.readCfgFile(fileName)

        self.bits = "".join([setting.value for setting in self.settings]).zfill(self.total)
        self.updated = True

    def sendUpdatedConfiguration(self,isI2C=False):
        """Sends updated bits to chip."""
        if isI2C:
            colutaMod.i2cWrite(self.coluta,self.tabName,self.channelName)
            # colutaMod.i2cWriteControl(self.coluta,self.tabName,self.channelName)
        else:
            self.coluta.fifoAWriteControl(self.tabName,self.channelName,reset=True)
        self.updated = False

    def readCfgFile(self):
        """For reading a fileName.cfg file

        Opens a config file, reads the settings from it, and decorates the settings
        attribute with a new list. Then, updates the bits attribute with this new
        set."""
        # First, open instance of the python config parser
        config = configparser.ConfigParser()
        config.optionxform=str
        # Make sure that the specified file exists. Throw warning if not.
        if not os.path.isfile(self.fileName):
            self.coluta.showError('Configuration file not found!')
        # Read in the file to the config instance
        config.read(self.fileName)
        # Check that the section is read properly
        if not config.has_section(self.sectionName):
            if not config.sections(): # No sections found at all!
                self.coluta.showError('Error reading config file. No sections found.')
            else: # Just the requested section wasn't found.
                self.coluta.showError('Error reading section '+self.sectionName+'.')
        
        # Read the data from the config file
        configItems = config.items(self.sectionName) # creates list of row keys
        # Get the total number of bits in the configuration section
        self.total = int(configItems[0][1])
        bitPos = self.total
        # Turn the list of tuples into a list of Settings objects (except TOTAL)
        self.settings = []
        for configAttribute in configItems[1:]:
            attributeName = configAttribute[0]
            attributeValue = configAttribute[1]
            bitPos-=len(attributeValue)
            if attributeName[0]=='+': # copy an existing setting
                originalCategory = self.coluta.configurations[attributeValue]
                originalSetting = originalCategory.getSetting(self.coluta,attributeName[1:])
                self.settings.append(originalSetting)
            else: # otherwise, create a new setting
                newSetting = Setting(*configAttribute,tab=self.tabName,channel=self.channelName,position=bitPos)
                self.settings.append(newSetting)

        # Create the names list
        self.names = [aSetting.name for aSetting in self.settings]
        # Create the bits string
        self.updateConfigurationBits()
        # # Update UI in the GUI
        # self.updateGUIText()

    def updateGUIText(self):
        coluta = self.coluta
        for setting in self.settings:
            settingName = setting.name
            # Skip filler and read-only bits
            if 'Fill' in settingName or settingName[-2:]=='__': continue
            boxName = setting.box # e.g. "coluta2ch1BLShiftBox"
            boxType = type(getattr(coluta,boxName))
            if boxType==QtWidgets.QPlainTextEdit:
                decimalString = str(colutaMod.binaryStringToDecimal(setting.value))
                getattr(coluta,boxName).document().setPlainText(decimalString)
            elif boxType==QtWidgets.QComboBox:
                setIndex = colutaMod.binaryStringToDecimal(setting.value)
                getattr(coluta,boxName).setCurrentIndex(setIndex)
            elif boxType==QtWidgets.QCheckBox:
                if setting.value=='1': getattr(coluta,boxName).setChecked(True) 
                elif setting.value=='0': getattr(coluta,boxName).setChecked(False)
                else: coluta.showError('CHIPCONFIGURATION: Error updating GUI. {}'.format(boxName))
            elif boxType==QtWidgets.QLabel:
                pass
            else:
                print('Could not find setting box {0}.'.format(boxName))

class Setting:
    """Basic class for setting"""
    def __init__(self,name,value,tab,channel='',position=0):
        self.name = name
        self.value = value
        self.length = len(value)
        self.position = position
        self.box = tab+channel+name+'Box'
        self.channel = channel
        self.tab = tab

    def __eq__(self,other):
        if self.channel==other.channel and \
           self.name==other.name and \
           self.value==other.value:
            return True

    def __ne__(self, other):
        return not self.__eq__(other)

def writeCfgFile(coluta,chip):
    """Writes a new config file. Will not overwrite the default file."""

    # Get the desired and default config file names
    fileNameBox = getattr(coluta,chip+'ConfigFileNameBox')
    newFileName = fileNameBox.toPlainText()
    newFileLast = newFileName.split('/')[-1]
    if newFileLast[-4:] != '.cfg':
        newFileName += '.cfg'
        newFileLast += '.cfg'
    defaultFileLast = getattr(coluta,chip+'defaultConfig').split('/')[-1]
    # If trying to overwrite the default, throw error and return
    if newFileLast == defaultFileLast:
        coluta.showError('Attempting to overwrite default .cfg file. Not allowed.')
        return

    # Open file and write the header
    outCfgFile = open(newFileName,'w')
    outCfgFile.write('# '+defaultFileLast+'\n')
    outCfgFile.write('\n')

    # Write the mandatory "Categories" section
    outCfgFile.write('[Categories]\n')
    configurations = getattr(coluta,chip+'Configurations')
    for categoryName in configurations:
        category = configurations[categoryName]
        outCfgFile.write( category.channelName+': '
                         +category.sectionName+'-'
                         +category.channelName+','
                         +str(category.address))
        if category.isI2C:
            outCfgFile.write(','+str(category.i2cAddress))#+','
                                # +str(category.adc))
        outCfgFile.write('\n')
    outCfgFile.write('\n')
    
    # Write sections for each category
    for categoryName in configurations:
        category = configurations[categoryName]
        outCfgFile.write('['+category.sectionName+'-'+category.channelName+']'+'\n')            
        outCfgFile.write('Total: '+str(len(category.bits))+'\n')
        for aSetting in category.settings:
            outCfgFile.write(aSetting.name+': '+aSetting.value+'\n')
        outCfgFile.write('\n')

    outCfgFile.close()

def overwrite(coluta,replacement):
    name = replacement.channelName # e.g. 'ch1'
    # First overwrite the direct member reference
    setattr(coluta,name,replacement)
    # Also need to overwrite the dictionary reference
    coluta.configurations[name] = getattr(coluta,name)
