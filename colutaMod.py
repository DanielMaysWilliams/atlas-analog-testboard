'''@package COLUTA65
Assorted helper functions for coluta operation

name: colutaMod.py
author: C. D. Burton
email: burton@utexas.edu
date: 2 February 2019
'''
import sys,os
import numpy as np
import serialMod
from math import ceil,floor
from PyQt5.QtCore import QThread
import Thread
import time

########################################################################################
# General helper functions

def openFileDialog(coluta,tabName,isConfigFile=True):
    from PyQt5.QtWidgets import QFileDialog
    dialog = QFileDialog()
    fileName = dialog.getOpenFileName(caption='Configuration File',directory='.')[0]
    relFileName = ''
    if os.path.isabs(fileName):
        relFileName = './'+os.path.relpath(fileName, '.')
    if isConfigFile and relFileName:
        setattr(coluta,tabName+'cfgFile',fileName)
        getattr(coluta,tabName+'ConfigFileNameBox').setPlainText(str(relFileName))
        if fileName is not '':
            configurations = getattr(coluta,tabName+'Configurations')
            coluta.setupConfigurations(configurations,fileName,tabName)
        coluta.sendUpdatedConfigurations()

def isMainThread():
    return not isBackgroundThread()

def isBackgroundThread():
    return isinstance(QThread.currentThread(),Thread.UnlockedThread)

########################################################################################
# Functions for PyInstaller

def resourcePath(relativePath):
    """Function to import external files when using PyInstaller.
    
    Get the absolute path to a resource. PyInstaller creates a temp folder and stores
    the path in _MEIPASS. If not using PyInstaller, the path should just be the current
    directory.
    """
    try:
        basePath = sys._MEIPASS
    except Exception:
        basePath = os.path.abspath('.')
    return os.path.join(basePath, relativePath)

########################################################################################
# Short helper functions to do simple conversions and operations

def byteArrayToString(inputByteArray):
    '''Convert raw data readout to a python string object.'''
    outputString = ''
    for byte in inputByteArray:
        outputString += '{0:08b}'.format(byte)
    return outputString

def decimalToBinaryString(decimal,length):
    '''Converts an int to bin to python string object.'''
    binary = bin(decimal)
    binaryString = str(binary)
    splitString = binaryString.split('b')[1]
    return splitString.zfill(length)

def binaryStringToDecimal(binaryString):
    '''Converts binary string to int.'''
    decimal = int(binaryString,2)
    return decimal

def findNearestMultiple(inputN, resolution):
    low = (ceil(inputN*resolution))/resolution
    high = (floor(inputN*resolution))/resolution
    return low if abs(low-inputN) < abs(high-inputN) else high

def checkDACSettings(coluta):
    dacAFlag = coluta.readDACA()
    dacBFlag = coluta.readDACB()
    dacReadBackFlags = dacAFlag and dacBFlag
    if dacReadBackFlags==False:
        print("ERROR: Readback for DAC does not match sent command")
        coluta.outputDataParser.dacError += 1
        coluta.outputDataParser.ignoreDataFile('histogram')

def checkReadBack(coluta,dataChannelName,categoryName,settingName=None):
    i2cChannels = ['global','ch1','ch2','exp1','exp2']
    # Do not perform readback if the channel is supposed to be ignored
    if categoryName in coluta.ignoreReadBack:
        return
    categoryReadBackFlag = coluta.checkControl(categoryName,settingName)
    if categoryReadBackFlag==False:
        print("ERROR: Readback for {} does not match sent command".format(categoryName))
        # coluta.stopRadiationRun() # Bomb out scenario
        coluta.outputDataParser.ignoreDataFile(dataChannelName)
        if categoryName=='histogram':
            coluta.outputDataParser.histogramError += 1
    else:
        coluta.logger.addEntry('SUCCESS','{0} readback was successful'.format(categoryName))
def checkPLLFlags(coluta):
    if coluta.checkControl('','misc','PLL_Locked__')!='1111':
        coluta.showError('COLUTAMOD: All PLL flags are not 1')
        return False
    return True

########################################################################################
# I2C functions

def makeI2CSubData(dataBits,wrFlag,readBackMux,subAddress,adcSelect):
    '''Combines the control bits and adds them to the internal address'''
    # {{dataBitsSubset}, {wrFlag,readBackMux,subAddress}, {adcSelect}}, pad with zeros
    return (dataBits+wrFlag+readBackMux+subAddress+adcSelect).zfill(64)

def makeWishboneCommand(dataBits,i2cWR,STP,counter,tenBitMode,chipIdHi,wrBit,chipIDLo,address):
    '''Arrange bits in the Wishbone standard order.'''
    wbTerminator = '00000000'
    wbByte0 = i2cWR+STP+counter
    wbByte1 = tenBitMode+chipIdHi+wrBit 
    wbByte2 = chipIDLo+address
    # dataBits = '0'*len(dataBits)
    bitsToSend = wbTerminator+dataBits+wbByte2+wbByte1+wbByte0
    # bitsToSend = wbTerminator+wbByte0+wbByte1+wbByte2+dataBits
    return bitsToSend

def makei2cInitCommand(WishboneCommand,STP,dataBitsSubset):
    '''Create the i2c init command.'''
    nBit = len(dataBitsSubset)
    nByte = int(np.ceil(nBit/8))
    dataBitsSubset = dataBitsSubset.zfill(nByte*8)
    # I2C bits follow, in order of MSB to LSB
    I2CWrite = WishboneCommand
    STP = STP
    dataCount = "{0:b}".format(nByte).zfill(4) # number of databytes as a binary string
    footer = '00000000'
    # STP, addr,WR_bit are parameters
    bitsToSend = I2CWrite+STP+dataCount+dataBitsSubset+footer
    return bitsToSend

def i2cInitCommand(coluta):
    '''Initialize the I2C communication in the FPGA.'''
    bits_zero = '00000000'

    # Experiment: rad board chip 10, cooled, zero deg pll0_c1
    #bits_f = '00001011' # Absolute minimum div. Any lower, it will ACK on all but settings are not applied
    #bits_f = '00001100' # More unstable
    # bits_f = '00001111' # Default. kinda unstable
    # bits_f = '00010100' # More stable?
    # bits_f = '00111111' # Ray-G-max div: more unstable  
    # bits_f = '00111000'
    bits_f = '00011111' # New default. From top_tb.v for testBoard.py

    bits_80 = '10000000'
    dataBitsSubset = str(bits_f+bits_zero+bits_80)
    nByte = 5
    address = 0
    dataBitsToSend = makei2cInitCommand('001','0',dataBitsSubset)
    reversedBitList = [dataBitsToSend[i:i+8] for i in range(0,len(dataBitsToSend),8)][::-1]
    reversedString = ''.join(reversedBitList)
    coluta.status.sendFifoAOperation(coluta,1,nByte,address)
    serialResult = serialMod.writeToChip(coluta,'A',reversedString)
    coluta.status.sendI2Ccommand(coluta)
    coluta.status.send(coluta)
    return serialResult

def i2cReadControl(coluta,tenBitMode='11110',
                          chipIdHi='00',
                          rdBit='1',
                          i2cRD='100',
                          STP='1',
                          chipIdLo='1',
                          i2cAddress=8,
                          wrBit='0',
                          i2cWR='010',
                          NTSP='0'):
    i2cAddressStr = '{0:07b}'.format(i2cAddress)
    WB_terminator = '0'*8
    WB_dataBits = '0'*64
    WB_4 = tenBitMode+chipIdHi+rdBit
    WB_3 = i2cRD+STP+'1001' #1011 is wrong, changed it to 1001: DP
    WB_2 = chipIdLo+i2cAddressStr
    WB_1 = tenBitMode+chipIdHi+wrBit
    WB_0 = i2cWR+NTSP+'0010'

    bitsToSend = WB_0+WB_1+WB_2+WB_3+WB_4+WB_dataBits+WB_terminator
    bitsReverse = [bitsToSend[i:i+8] for i in range(0,len(bitsToSend),8)][::-1]
    bitsToSend = ''.join(bitsReverse)

    nBits = len(bitsToSend)
    nByte = int(nBits/8) # should be 14
    coluta.status.send(coluta)
    serialMod.flushBuffer(coluta)
    coluta.status.sendFifoAOperation(coluta,1,nByte,0)
    serialResult = serialMod.writeToChip(coluta,'A',bitsToSend)
    coluta.status.sendI2Ccommand(coluta)
    coluta.status.send(coluta)
    time.sleep(0.1)
    
    nBytesExpected = 8 if i2cAddress==8 else 6
    # Read the I2C output
    coluta.status.sendFifoAOperation(coluta,2,nBytesExpected,0)
    # Read the relevant bytes
    i2cOutput = serialMod.readFromChip(coluta,'A',nBits-6*8)[:nBytesExpected]
    coluta.status.send(coluta)
    # Convert the bytes into bits and turn into a string
    return byteArrayToString(i2cOutput)

def i2cWriteControl(coluta,chip,categoryName):
    """Same as fifoAWriteControl(), except for I2C."""
    configurations = getattr(coluta,chip+'Configurations')
    category = configurations[categoryName] # e.g. "global"
    address = category.address # Always 0 for I2C
    controlBits = category.bits # Concatenated configuration bits
    i2cAddress = int(category.i2cAddress) # Specifies the I2C address
    adc = category.adc
    # if chip=='coluta1' and coluta.coluta1globalEnableSCclockBox.isChecked():
    #     adc = '00001111'
    # elif chip=='coluta2' and coluta.coluta2globalEnableSCclockBox.isChecked():
    #     adc = '00001111'
    maxWriteAttempts = 100
    if len(controlBits)>64:
        # We then need to split up control data which has more than 64 bits. We still only 
        # have 64 bits to use, but 16 of these bits are then needed for sub-address, etc.
        # Therefore, we will split into chuncks of 48 bits and send N/48 I2C commands. If
        # the number of bits is not a multiple of split, we pad on the left to make it so.
        split = 48
        # controlBits = controlBits.zfill(ceil(len(controlBits)/split)*split)
        # We need to split up the control bits into chuncks of 48 bits. 
        # For subaddress 5 bits, we need to overwrite 16 bits from the previous sub address bits
        # Get the first four subaddresses. So get subaddress 0,3,6, and 9
        subAddressList = [3*i for i in range( int( np.floor(len(controlBits)/split) ) )]
        # Now add the last subaddress. So to send the last 32 bits, you need to send them to subaddress 11
        # For 224 bits, (224 - 48)/16 = 11. Append the final subaddress to the subAddressList and reverse the list
        subAddressList.append( int( (len(controlBits)-split)/16 ) )
        subAddressList.reverse()
        # We then need to split up control data which has more than 64 bits. We still only 
        # have 64 bits to use, but 16 of these bits are then needed for sub-address, etc.
        # Therefore, we will split into chuncks of 48 bits and send N/48 I2C commands. If
        # the number of bits is not a multiple of split, we use bits from previous I2C command
        # to get 48 bits for the I2C command.
        # Create the list of the MSB indices
        MSBBitList = [ len(controlBits)-48*(i+1) if (len(controlBits)-48*(i+1)>0) else 0 for i in range(len(subAddressList))]
        MSBBitList.reverse()
        # Create the list of LSB indices
        LSBBitList = [ msb+48 for msb in MSBBitList]
        # Create the list of data bits to send 
        dataBitsList = []
        for msb,lsb in zip(MSBBitList,LSBBitList):
            dataBitsList.append(controlBits[msb:lsb])

        # Then, we need to make i2c commands out of each these chunks
        dataBitsToSendList = []
        for dataBits,subAddress in zip(dataBitsList,subAddressList):
            subAddrStr = '{0:06b}'.format(subAddress)
            dataBitsToSendList.append(makeI2CSubData(dataBits,'1','0',subAddrStr,adc))


    elif len(controlBits) == 64:
        dataBitsToSendList = [controlBits]

    else: 
        coluta.showError('COLUTAMOD: Unknown configuration bits.')

    for dataBitsToSend in dataBitsToSendList:
        ackReceived = False
        usbReceived = False
        serialResult = False
        nAttempts = 0
        # while not ackReceived and nAttempts<maxWriteAttempts:
        # while not serialResult:
        # print('{0:02x}'.format([dataBitsToSend[i:i+8] for i in range(0,len(dataBitsToSend),8)]))
        # print([dataBitsToSend[i:i+8] for i in range(0,len(dataBitsToSend),8)])
        serialResult = attemptWrite(coluta,dataBitsToSend,i2cAddress,address)
            # check the misc register
            # ackReceived = coluta.checkControl('misc__','Last_I2C_ACK__')
            # nAttempts += 1
            # # if not (ackReceived and usbReceived):
            # if coluta.debug:
            #     if not ackReceived: print('NOACK received. Attempt',nAttempts)
            #     else: print('ACK RECEIVED')
            # time.sleep(0.05)
        # if nAttempts==maxWriteAttempts:
        #     coluta.logger.addEntry('ERROR','I2C-Write')
    return serialResult

def i2cReadBack(coluta,chip,categoryName,i2cAddress):
    """
    Read back I2C commands
    For global bits, call i2cReadControl
    For other bits, follow the procedure below:
    1.) Write i2c command to correct subaddress with 48 bits of zeros
    2.) Read back using i2cReadControl
    3.) Repeat steps two and three till all bits are received
    """
    configurations = getattr(coluta,chip+'Configurations')
    maxReadAttempts, maxWriteAttempts = 0,0
    nReadAttempts = 0
    if categoryName == 'global':
        bitsFromConfig = configurations[categoryName].bits
        readBackBits = ''
        readBackBits = i2cRead(coluta,chip,categoryName)
        # bitsReceived = i2cReadControl(coluta,i2cAddress=i2cAddress)

    else:
        category = configurations[categoryName]
        adcAddress = category.adc
        split = 48
        bitsExpected = category.bits
        numBitsExpected = len(bitsExpected)
        address = category.address

        # Make the subAddress list. Same logic as creating the subAddress list for i2cWriteControl()
        subAddressList = [3*i for i in range( int( np.floor(numBitsExpected/split) ) )]
        subAddressList.append( int( (numBitsExpected-split)/16 ) )
        subAddressList.reverse()
        
        # Create the list data bits to compare with i2cReadControl() output
        # Create the list of the MSB indices
        MSBBitList = [ len(bitsExpected)-48*(i+1) if (len(bitsExpected)-48*(i+1)>0) else 0 for i in range(len(subAddressList))]
        MSBBitList.reverse()
        # Create the list of LSB indices
        LSBBitList = [ msb+48 for msb in MSBBitList]
        # Create the list of data bits to send 
        bitList = []
        for msb,lsb in zip(MSBBitList,LSBBitList):
            bitList.append(bitsExpected[msb:lsb])
        
        dataBitsList = ['0'*32,'0'*48,'0'*48,'0'*48,'0'*48]
        dataBitsToSendList = []

        for subAddress,dataBits in zip(subAddressList,dataBitsList):
            subAddStr = '{0:06b}'.format(subAddress)
            dataBitsToSendList.append(makeI2CSubData(dataBits,'0','1',subAddStr,adcAddress))

        i2cReadBackList = []
        for idx,(dataBitsToSend,subAddress) in enumerate(zip(dataBitsToSendList,subAddressList)):
            serialResult = attemptWrite(coluta,dataBitsToSend,i2cAddress,address)
            # serialResult = attemptWriteNew(coluta,chip,dataBitsToSend,i2cAddress,address,0)
            bitsReceived = ''
            bitsFromConfig = bitList[idx]
            # bitsReceived = i2cReadControl(coluta,i2cAddress=i2cAddress)
            bitsReceived = i2cRead(coluta,chip,categoryName)
            print('received',bitsReceived)
            # bitsReceived = i2cRead(coluta,chip,categoryName,i2cAddress=i2cAddress)
            # For the last sub address (subAddr 11) append only the first 32 bits.
            # The last 16 bits are overlapped bits from subAddr 9 data bits
            if subAddress%3 != 0:
                i2cReadBackList.append(bitsReceived[:32])
            else:
                i2cReadBackList.append(bitsReceived)
        readBackBits = ''.join(i2cReadBackList)
    # print(readBackBits)
    return readBackBits

def i2cReadLpGBT(coluta,i2cWR='010',
                        NSTP='0',
                        i2cRD='100',
                        STP='1',
                        lpgbtAddress='1110000',
                        wrBit='0',
                        rdBit='1',
                        lpgbtRegAddress=-1):

    if lpgbtRegAddress == -1:
        try:
                lpgbtRegAddress = int(coluta.controlLpGBTRegisterAddressBox.toPlainText())
        except Exception:
            coluta.showError('LpGBT: Invalid register address')
            return '00'
    coluta.selectI2CinterfaceAndCalPulses(fifoOperation=1,auxRegAddress=0)
    lpgbtRegAddressStr = '{0:016b}'.format(lpgbtRegAddress)
    WB_terminator = '0'*8
    WB_dataBits = '0'*8
    WB_5 = lpgbtAddress+rdBit
    WB_4 = i2cRD+STP+'0010'
    WB_3 = lpgbtRegAddressStr[0:8] # [15:8] in testbench, i.e. MSBs
    WB_2 = lpgbtRegAddressStr[8:16] # [7:0] in testbench, i.e. LSBs
    WB_1 = lpgbtAddress+wrBit
    WB_0 = i2cWR+NSTP+'0011'

    bitsToSend = WB_0+WB_1+WB_2+WB_3+WB_4+WB_5+WB_dataBits+WB_terminator
    bitsReverse = [bitsToSend[i:i+8] for i in range(0,len(bitsToSend),8)][::-1]
    bitsToSend = ''.join(bitsReverse)

    nBits = len(bitsToSend)
    nByte = int(nBits/8) # should be 8
    coluta.status.send(coluta)
    serialMod.flushBuffer(coluta)
    coluta.status.sendFifoAOperation(coluta,1,nByte,0)
    serialResult = serialMod.writeToChip(coluta,'A',bitsToSend)
    coluta.status.sendI2Ccommand(coluta)
    coluta.status.send(coluta)
    nWordsExpected = 1
    # Read the I2C ouput
    serialMod.flushBuffer(coluta)
    coluta.status.sendFifoAOperation(coluta,2,nWordsExpected,0)
    # i2cOutput = serialMod.readFromChip(coluta,'A',nBits-6*8)
    time.sleep(0.01) # Wait for the buffer to fill
    i2cOutput = serialMod.readFromChip(coluta,'A',8) # Need to think about nBytes argument for readFromChip()
    # Read the relevant bytes
    if type(i2cOutput) is not bool:
        # i2cOutput = i2cOutput[:8]
        i2cOutput = i2cOutput[:1]
    else:
        i2cOutput = bytearray(0)
    coluta.status.send(coluta)
    # Convert the bytes into bits and turn into a string
    # return byteArrayToString(i2cOutput)
    return ["{:02x}".format(x) for x in i2cOutput]

def i2cWriteLpGBT(coluta,
                  i2cWR='010',
                  STP='1',
                  lpgbtAddress='1110000',
                  wrBit='0',
                  lpgbtRegAddress=32,
                  dataWord='11001000'):

    # lpgbtRegAddress = category.address
    # dataWord = category.bits # Concatenated configuration bits
    address = 0 # i2c is at 0
    i2cAddress = 0 # Always 0 for I2C
    maxWriteAttempts = 100
    try:
        lpgbtRegAddress = int(coluta.controlLpGBTRegisterAddressBox.toPlainText())
    except Exception:
        coluta.showError('LpGBT: Invalid register address')
        return '00'
    dataWord = coluta.controlLpGBTRegisterValueBox.toPlainText()
    if len(dataWord)==0 or len(dataWord)>8:
        coluta.showError('LpGBT: Setting overflow! Max value 8 bits')
        return False
    # Activate the I2C interface
    coluta.selectI2CinterfaceAndCalPulses(fifoOperation=1,auxRegAddress=0)
    # lpgbtRegAddressStr = '{0:016b}'.format(int(lpgbtRegAddress,16))
    lpgbtRegAddressStr = '{0:016b}'.format(lpgbtRegAddress)
    # headerBits = '0'*80
    wbTerminator = '0'*8
    dataBits = dataWord
    wbByte3 = lpgbtRegAddressStr[0:8] # [15:8] in testbench, i.e. MSBs
    wbByte2 = lpgbtRegAddressStr[8:16] # [7:0] in testbench, i.e. LSBs
    wbByte1 = lpgbtAddress+wrBit
    wbByte0 = i2cWR+STP+'0100'

    bitsToSend = wbTerminator+dataBits+wbByte3+wbByte2+wbByte1+wbByte0
    # bitsReverse = [bitsToSend[i:i+8] for i in range(0,len(bitsToSend),8)][::-1]
    # bitsToSend = ''.join(bitsReverse)
    nByte = int(len(bitsToSend)/8) # should be 6
    ackReceived = False
    serialResult = False
    nAttempts = 0
    # while not ackReceived and nAttempts<maxWriteAttempts:
    #while not serialResult:
    coluta.status.send(coluta)
    coluta.status.sendFifoAOperation(coluta,1,nByte,address)
    serialResult = serialMod.writeToChip(coluta,'A',bitsToSend)
    coluta.status.sendI2Ccommand(coluta)
        # serialResult = attemptWrite(coluta,dataBitsToSend,i2cAddress,address)

        # ackReceived = coluta.checkControl('misc__','Last_I2C_ACK__')
        # nAttempts += 1
        # if coluta.debug:
        #    if not ackReceived: print('NOACK received. Attempt',nAttempts)
        #    else: print('ACK RECEIVED')
            # print('Attempt', nAttempts)
    #     time.sleep(0.05)
    # if nAttempts == maxWriteAttempts:
    #     coluta.logger.addEntry('ERROR','I2C-lpBGT-Write')

    return serialResult


def i2cRead(coluta,chip,categoryName,
            i2cWR='010',
            NSTP='0',
            i2cRD='100',
            STP='1',
            wrBit='0',
            rdBit='1',
            lpgbtAddress='1110000',
            lpgbtRegAddress='32',
            tenBitMode='11110',
            chipIdHi='00',
            chipIdLo='1',
            i2cAddress=8):
    configurations = getattr(coluta,chip+'Configurations')
    category = configurations[categoryName]

    WB_terminator = '0'*8

    if chip == 'lpgbt':
        coluta.selectI2Cinterface(fifoOperation=1,auxRegAddress=0)
        lpgbtRegAddress = category.address
        lpgbtRegAddress = lpgbtRegAddress
        lpgbtRegAddressStr = '{0:016b}'.format(int(lpgbtRegAddress))
        # lpgbtRegAddressStr = '{0:016b}'.format(453)
        WB_dataBits = '0'*8
        WB_5 = lpgbtAddress + rdBit
        WB_4 = i2cRD + STP + '0010'
        WB_3 = lpgbtRegAddressStr[0:8]  # [15:8] in testbench, i.e. MSBs
        WB_2 = lpgbtRegAddressStr[8:16]  # [7:0] in testbench, i.e. LSBs
        WB_1 = lpgbtAddress + wrBit
        WB_0 = i2cWR + NSTP + '0011'
        partialBitsToSend = WB_0+WB_1+WB_2+WB_3+WB_4+WB_5+WB_dataBits

        nBytesExpected = 1
        nWordsExpected = 1

    elif chip[:-1] == 'coluta':
        if chip[-1] == '1':
            coluta.selecti2cinterface(fifooperation=1, auxregaddress=1)
        elif chip[-1] == '2':
            coluta.selecti2cinterface(fifooperation=1, auxregaddress=2)
        configurations = getattr(coluta,chip+'Configurations')
        category = configurations[categoryName] # e.g. "global"
        # address = category.address # Always 0 for I2C
        i2cAddress = int(category.i2cAddress)
        i2cAddressStr = '{0:07b}'.format(i2cAddress)
        # WB_dataBits = category.bits
        WB_dataBits = '0'*64
        WB_4 = tenBitMode + chipIdHi + rdBit
        WB_3 = i2cRD + STP + '1001'  # 1011 is wrong, changed it to 1001: DP
        WB_2 = chipIdLo + i2cAddressStr
        WB_1 = tenBitMode + chipIdHi + wrBit
        WB_0 = i2cWR + NSTP + '0010'
        partialBitsToSend = WB_0+WB_1+WB_2+WB_3+WB_4+WB_dataBits

        # nBytesExpected = 1 if i2cAddress==8 else 6 
        # For TB, we need to multiples of 16, so nBytesExpected = 1 ==> 16 bytes expected
        # Output from FIFO comes in chunks of 16 bytes at once.
        nWordsExpected = 1
        # nBytesExpected = 1 if i2cAddress==8 else 2

    else:
        coluta.showError('COLUTAMOD: Unknown chip name.')
        return False

    bitsToSend = partialBitsToSend+WB_terminator
    bitsReverse = [bitsToSend[i:i+8] for i in range(0,len(bitsToSend),8)][::-1]
    bitsToSend = ''.join(bitsReverse)

    nBits = len(bitsToSend)
    nByte = int(nBits/8) # should be 8 for lpgbt, 14 for coluta
    # nByte = 1
    coluta.status.send(coluta)
    serialMod.flushBuffer(coluta)
    coluta.status.sendFifoAOperation(coluta,1,nByte,0)
    serialResult = serialMod.writeToChip(coluta,'A',bitsToSend)
    coluta.status.sendI2Ccommand(coluta)
    coluta.status.send(coluta)
    time.sleep(0.1)

    # Read the I2C ouput
    # serialMod.flushBuffer(coluta)
    coluta.status.sendFifoAOperation(coluta,2,nWordsExpected,0)
    # i2cOutput = serialMod.readFromChip(coluta,'A',nBits-6*8)
    time.sleep(0.1)
    i2cOutput = serialMod.readFromChip(coluta,'A',8) # Need to think about nBytes argument for readFromChip()
    # Read the relevant bytes
    if type(i2cOutput) is not bool:
        i2cOutput = i2cOutput[:8]
    else:
        i2cOutput = bytearray(0)
    # coluta.status.send(coluta)
    # Convert the bytes into bits and turn into a string
    return byteArrayToString(i2cOutput)

def i2cWrite(coluta,chip,categoryName):
    """Same as fifoAWriteControl(), except for I2C."""
    configurations = getattr(coluta,chip+'Configurations')
    category = configurations[categoryName] # e.g. "global"
    address = category.address # Always 0 for I2C
    controlBits = category.bits # Concatenated configuration bits
    # adc = category.adc
    if chip=='coluta1': #  and coluta.coluta1globalEnableSCclockBox.isChecked():
        coluta.selectI2CinterfaceAndCalPulses(fifoOperation=1,auxRegAddress=1)
        adc = category.adc
        # adc = '00001111' if coluta.coluta1globalEnableSCclockBox.isChecked() else category.adc
        address = category.address
        i2cAddress = int(category.i2cAddress) # Specifies the I2C address
        lpgbtRegAddress = 0 # just to have a value assigned
    elif chip=='coluta2': #  and coluta.coluta2globalEnableSCclockBox.isChecked():
        coluta.selectI2CinterfaceAndCalPulses(fifoOperation=1,auxRegAddress=2)
        adc = category.adc
        #adc = '00001111' if coluta.coluta2globalEnableSCclockBox.isChecked() else category.adc
        address = category.address
        i2cAddress = int(category.i2cAddress) # Specifies the I2C address
        lpgbtRegAddress = 0 # just to have a value assigned
    elif chip=='lpgbt':
        coluta.selectI2CinterfaceAndCalPulses(fifoOperation=1,auxRegAddress=0)
        address = category.i2cAddress
        lpgbtRegAddress = category.address
        i2cAddress = 0 # just to have a value assigned
        category.updated = False # TODO: should probably delete this at some point

    maxWriteAttempts = 100
    if len(controlBits)>64 and chip[:-1]=='coluta':
        # We then need to split up control data which has more than 64 bits. We still only
        # have 64 bits to use, but 16 of these bits are then needed for sub-address, etc.
        # Therefore, we will split into chuncks of 48 bits and send N/48 I2C commands. If
        # the number of bits is not a multiple of split, we pad on the left to make it so.
        split = 48
        # controlBits = controlBits.zfill(ceil(len(controlBits)/split)*split)
        # We need to split up the control bits into chuncks of 48 bits.
        # For subaddress 5 bits, we need to overwrite 16 bits from the previous sub address bits
        # Get the first four subaddresses. So get subaddress 0,3,6, and 9
        subAddressList = [3*i for i in range( int( np.floor(len(controlBits)/split) ) )]
        # Now add the last subaddress. So to send the last 32 bits, you need to send them to subaddress 11
        # For 224 bits, (224 - 48)/16 = 11. Append the final subaddress to the subAddressList and reverse the list
        subAddressList.append( int( (len(controlBits)-split)/16 ) )
        subAddressList.reverse()
        # We then need to split up control data which has more than 64 bits. We still only
        # have 64 bits to use, but 16 of these bits are then needed for sub-address, etc.
        # Therefore, we will split into chuncks of 48 bits and send N/48 I2C commands. If
        # the number of bits is not a multiple of split, we use bits from previous I2C command
        # to get 48 bits for the I2C command.
        # Create the list of the MSB indices
        MSBBitList = [ len(controlBits)-48*(i+1) if (len(controlBits)-48*(i+1)>0) else 0 for i in range(len(subAddressList))]
        MSBBitList.reverse()
        # Create the list of LSB indices
        LSBBitList = [ msb+48 for msb in MSBBitList]
        # Create the list of data bits to send
        dataBitsList = []
        for msb,lsb in zip(MSBBitList,LSBBitList):
            dataBitsList.append(controlBits[msb:lsb])

        # Then, we need to make i2c commands out of each these chunks
        dataBitsToSendList = []
        for dataBits,subAddress in zip(dataBitsList,subAddressList):
            subAddrStr = '{0:06b}'.format(subAddress)
            dataBitsToSendList.append(makeI2CSubData(dataBits,'1','0',subAddrStr,adc))


    elif len(controlBits) == 64 or chip == 'lpgbt':
        dataBitsToSendList = [controlBits]

    else:
        coluta.showError('COLUTAMOD: Unknown configuration bits for chip {0}.'.format(chip))

    for dataBitsToSend in dataBitsToSendList:
        serialResult = attemptWriteNew(coluta,chip,dataBitsToSend,i2cAddress,address,lpgbtRegAddress)
        # serialResult = attemptWrite(coluta,dataBitsToSend,i2cAddress,address)
        # time.sleep(0.05)

    return serialResult

def attemptWriteNew(coluta,chip,dataBitsToSend,i2cAddress,address,lpgbtRegAddress):
    nDataBytes = int(len(dataBitsToSend)/8) # should be 8 for coluta, 1 for lpgbt
    if chip=='lpgbt':
        nDataBytes += 3 # should be 4
    elif chip=='coluta1':
        nDataBytes += 2 # should be 10
    elif chip=='coluta2':
        nDataBytes += 2 # should be 10
        
    nDataBytesStr = '{0:04b}'.format(nDataBytes)

    lpgbtRegAddressStr = '{0:016b}'.format(lpgbtRegAddress)
    i2cAddressStr = '{0:07b}'.format(i2cAddress)

    bitsToSend = makeWishboneCommandNew(dataBitsToSend,chip,'010','1',nDataBytesStr,'0','11110','00','1',
                                        i2cAddressStr,'1110000',lpgbtRegAddressStr)
    nByte = int(len(bitsToSend)/8) # should be 12 for coluta, 6 for lpgbt
    coluta.status.send(coluta)
    coluta.status.sendFifoAOperation(coluta,1,nByte,address)
    serialResult = serialMod.writeToChip(coluta,'A',bitsToSend)
    coluta.status.sendI2Ccommand(coluta)

    return serialResult


def makeWishboneCommandNew(dataBits,chip,i2cWR,STP,counter,wrBit,tenBitMode,chipIdHi,chipIDLo,
                           address,lpgbtAddress, lpgbtRegAddressStr):
    '''Arrange bits in the Wishbone standard order.'''
    wbTerminator = '00000000'
    wbByte0 = i2cWR+STP+counter

    if chip == 'lpgbt':
        wbByte1 = lpgbtAddress+wrBit
        wbByte2 = lpgbtRegAddressStr[8:16] # [7:0] in testbench, i.e. LSBs
        wbByte3 = lpgbtRegAddressStr[0:8] # [15:8] in testbench, i.e. MSBs
        bitsToSend = wbTerminator+dataBits+wbByte3+wbByte2+wbByte1+wbByte0

    elif chip[:-1] == 'coluta':
        wbByte1 = tenBitMode+chipIdHi+wrBit
        wbByte2 = chipIDLo+address
        bitsToSend = wbTerminator+dataBits+wbByte2+wbByte1+wbByte0

    return bitsToSend


def readSEU(coluta,chip='coluta1',categoryName='ch1'):
    '''Read back SEU counter'''
    configurations = getattr(coluta,chip+'Configurations')
    # category = getattr(coluta,'ch1')
    category = configurations[categoryName]
    adcAddress = category.adc
    i2cAddress = category.i2cAddress
    address = category.address
    dataBits = 48*'0'
    subAddressStr = '{0:06b}'.format(16)
    dataBitsToSend = makeI2CSubData(dataBits,'0','1',subAddressStr,adcAddress)
    maxWriteAttempts, maxReadAttempts = 200, 200
    writeACKFlag = False
    writeUSBFlag = False
    nWriteAttempts = 0 
    while not (writeACKFlag and writeUSBFlag) and nWriteAttempts<maxWriteAttempts:
        serialResult = attemptWriteNew(coluta,chip,dataBitsToSend,i2cAddress,address,0)
        writeACKFlag = coluta.checkControl('misc__','Last_I2C_ACK__')
        writeUSBFlag = coluta.checkControl('misc__','I2C_USB_done__')
        nWriteAttempts +=1
        if coluta.debug:
            if not writeACKFlag: print('NOACK received. Attempt',nWriteAttempts)
            else: print('ACK RECEIVED')
        time.sleep(0.05)
    if nWriteAttempts==maxWriteAttempts:
        coluta.logger.addEntry('ERROR','SEU-Readback')
        coluta.status.sendColutaReset(coluta)
        i2cInitCommand(coluta)
        coluta.configurations = {}   
        coluta.setupConfigurations(coluta.cfgFile)
        coluta.sendUpdatedConfigurations()
        coluta.outputDataParser.i2cError+=1
        return 15*'1'
    readACKFlag = False
    readUSBFlag = False
    nReadAttempts = 0
    bitsReceived = 15*'1'
    while (not(readUSBFlag and readACKFlag)) and bitsReceived == 15*'1' and nReadAttempts<maxReadAttempts:
        bitsReceived = i2cReadControl(coluta,i2cAddress=i2cAddress)[:15]
        readACKFlag = coluta.checkControl('misc__','Last_I2C_ACK__')
        readUSBFlag = coluta.checkControl('misc__','I2C_USB_done__')
        nReadAttempts += 1

    if nReadAttempts==maxReadAttempts:
        coluta.logger.addEntry('ERROR','SEU-Readback')
        coluta.status.sendColutaReset(coluta)
        i2cInitCommand(coluta)
        coluta.configurations = {}   
        coluta.setupConfigurations(coluta.cfgFile)
        coluta.sendUpdatedConfigurations()
        coluta.outputDataParser.i2cError+=1
        return 15*'1'

    return bitsReceived


def attemptWrite(coluta,dataBitsToSend,i2cAddress,address):
    nDataBytes = int(len(dataBitsToSend)/8)+2 # should be 10
    nDataBytesStr = '{0:04b}'.format(nDataBytes)
    i2cAddressStr = '{0:07b}'.format(i2cAddress)
    bitsToSend = makeWishboneCommand(dataBitsToSend,'010','1',nDataBytesStr,'11110','00','0','1',i2cAddressStr)

    nByte = int(len(bitsToSend)/8) # should be 12

    # nByte = int(len(bitsToSend)/8) - 1 
    # bitsToSend = bitsToSend[8:]

    coluta.status.send(coluta)
    # time.sleep(1)
    coluta.status.sendFifoAOperation(coluta,1,nByte,address)
    # time.sleep(2)
    serialResult = serialMod.writeToChip(coluta,'A',bitsToSend)
    # time.sleep(1)
    coluta.status.sendI2Ccommand(coluta)
    coluta.status.send(coluta)
    return serialResult

########################################################################################
# FFT-related functions

def doFFT(coluta,adcData):
    fourier = list(map(lambda x: np.sqrt(x.real**2 + x.imag**2), np.fft.fft(adcData)[2:-2]))
    fourier = fourier[:round(len(fourier)/2)]
    fourier = fourier/np.max(fourier)

    psd = 20*np.log10(fourier)
    freq = np.linspace(0,coluta.frequency/2,len(fourier))
    QA = performance(fourier,coluta.frequency)
    return freq,psd,QA

def performance(fourier,fs):
    '''Calculates performance measures of FFT.'''
    return {'SINAD': SINAD(fourier),
            'SNR': SNR(fourier,fs),
            'ENOB': ENOB(fourier),
            'SFDR': SFDR(fourier)}

def SINAD(fourier):
    sum2 = 0
    for normBin in fourier:
        if normBin==1: continue
        sum2 += normBin**2
    return -10*np.log10(sum2)

def SFDR(fourier):
    #print(np.delete(fourier,np.where(fourier==1)))
    return -20*np.log10(np.max(np.delete(fourier,np.where(fourier==1))))

def SNR(fourier,fs,K=2):
    try:
        freq = np.linspace(0,fs/2,len(fourier))
        fa = freq[np.argmax(fourier)]
        fr = fs/fa
    except:
        print("Error: Division by 0")
        fr = 0

    noHarmonics = np.array(fourier,copy=True)
    harmList = harmonics(fs,fa)
    for i,k in enumerate(freq):
        for h in harmList:
            if abs(k-h)<1e-6:
                noHarmonics[i]=0
    return SINAD(noHarmonics)

def ENOB(fourier):
    return (SINAD(fourier)-1.76)/6.02

def harmonics(fs,fa,K=2):
    fr = fs/fa
    fn = fs/2
    try:
        harmList = [((k*fa+fn)%fs)-fn for k in np.arange(2,int(fr*K))]
    except:
        harmList = []
    return harmList
