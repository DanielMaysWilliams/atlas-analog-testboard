"""Communicates read and write messages to the chip.

name: serialMod.py
author: D. Panchal, C. D. Burton
email: dpanchal@utexas.edu, burton@utexas.edu
date: 15 April 2019
"""

import serial
import serial.tools.list_ports as LP
import time
import sys
from platform import system
from PyQt5 import QtWidgets,QtCore
from PyQt5.QtCore import QThread,QMutex
import Thread

def findPorts(coluta):
    """Finds the locations of the USB chip in a platform-independent way."""
    # Check which system is being used, and pass it to Qt
    platform = system()
    coluta.platform = platform
    # Description is something like 'COLUTA65V1A' (for version 1 chip)
    description = coluta.description
    # We will create a list of ftdi devices, which are obtained in a different way
    # for each platform
    ftdiDevices = []
    if platform=='Windows':
        ports = LP.comports()
        # If no ports found, then show the error and exit the script
        if ports is None:
            print('No ports found, exiting...')
            QtCore.QCoreApplication.instance().quit
        # Windows sees the USB as a Serial COM port, so PySerial cannot see the 
        # description of the USB. However, the manufacturer is still 'FTDI', so 
        # we can at least find these ports. The only case where this might fail 
        # is when more than one FTDI device is hooked up to the same computer. 
        # This is handeled with an exception, and the GUI refuses to connect. 
        # Finally the last number of the serial number is A or B, which is the 
        # channel identifier.
        for port in ports:
            if port is None: continue
            device = port.device
            manufac = port.manufacturer
            if manufac is not None and manufac!='FTDI': continue
            channel = port.serial_number[:2] # Serial number configured to be "ABxxxxxx"
            ftdiDevices.append((channel,device))
            coluta.serial_number = port.serial_number
    elif platform=='Darwin' or platform=='Linux':
        # OS X and Linux see the description of the USB, so we can grep for the 
        # ports that match. If the ports' names end in 'A' and 'B', we add them.
        # If they end in '0' and '1', we change them to 'A' and 'B', respectively.
        ports = LP.grep(description)
        # If no ports found, then show the error and exit the script
        if ports is None:
            print('No ports found, exiting...')
            QtCore.QCoreApplication.instance().quit

        for port in ports:
            if port is None: continue
            device = port.device
            print(device)
            description = port.description
            print(description)
            channel = description[-2:] # Configure a channel name
            print(channel)
            ftdiDevices.append((channel,device))
            print(ftdiDevices)
            coluta.serial_number = port.description
    else:
        # Chrome OS is not supported :(
        print('Unknown platform {}'.format(platform))
        QtCore.QCoreApplication.instance().quit
    nDevice = len(ftdiDevices)
    deviceDict = dict(ftdiDevices)
    # Ensure that only 1 USB port is added.
    if nDevice!=1:
        warning = '{0} USB ports found matching {1}'.format(nDevice,description)
        coluta.showError(warning)
    # Finally, return the names of the ports
    return deviceDict

def setupSerials(coluta):
    """Sets up Serial objects for the GUI."""
    try:
        fifoA = serial.Serial( port     = coluta.port,
                               baudrate = coluta.baudrate,
                               parity   = coluta.parity,
                               stopbits = coluta.stopbits,
                               bytesize = coluta.bytesize,
                               timeout  = coluta.timeout,
                               write_timeout = coluta.timeout )
        return fifoA
    except:
        coluta.showError('Unable to connect to chip.')
        return None

def checkSerials(coluta):
    """Check validity of serial connections"""
    # For UNIX platforms, is serial.serialposix.Serial
    # For Windows platforms, is serial.serialwin32.Serial
    pf = coluta.platform
    if pf=='Windows':
        serialType = serial.serialwin32
    elif pf=='Darwin' or pf=='Linux':
        serialType = serial.serialposix

    print(type(coluta.serial))
    isPortConnected = isinstance(coluta.serial, serialType.Serial)
    if not isPortConnected:
        coluta.showError('SERIALMOD: Handshaking procedure failed. Not connected.')

    return isPortConnected

def writeToChip(coluta,port,message):
    """Writes a given message into the given port."""
    # Check message type and convert if necessary
    messageType = type(message)
    if messageType is type(bytearray()):
        BAMessage = message
    elif messageType is type(list()) and len(message)>0:
        if type(message[0])==type(int()) and all([0<=i<=255 for i in message]):
            BAMessage = bytearray(message)
        else:
            coluta.showError('SERIALMOD: Message is not of a supported type.')
            return False
    elif messageType is type(str()) and len(message)>0:
        BAMessage = bytearray(int(message, 2).to_bytes(len(message)//8, byteorder='big'))
    else:
        coluta.showError('SERIALMOD: Message is not of a supported type.')
        return False
    
    # Get the serial object corresponding to the correct channel
    try:
        fifo = coluta.serial
    except Exception: 
        fifo = None

    # Debug statements
    messageList = []
    for byteMessage in BAMessage:
        messageList.append(format(byteMessage, "02x"))
    if coluta.debug:
        print('{} <-'.format(port)," ".join(messageList))

    if fifo==None:
        if coluta.pOptions.no_connect:
            return True
        else:
            coluta.showError('SERIALMOD: Port {} not connected.'.format(port))
            return False

    # Block an unlocked thread before writing to chip
    # block = Thread.block()
    # coluta.logger.addTraceback("{0} <- {1}".format(port, " ".join(messageList)))
    time.sleep(0.1)
    nBytesWritten = fifo.write(BAMessage)
    time.sleep(0.01)
    assert nBytesWritten==len(BAMessage), "SERIALMOD: wrote {0} bytes, had to write {1} bytes".format(nBytesWritten,len(BAMessage))
    # If an unlocked thread was blocked, release the lock
    # Thread.block(block)    
    return True

def readFromChip(coluta,port,nBytes):
    """Reads bytes from the chip."""
    # Check that positive number of bytes requested.
    if nBytes<=0:
        coluta.showError('SERIALMOD: Non-positive number of bytes requested.')

    # Get the serial object corresponding to the correct channel
    fifo = coluta.serial

    # Debug statements
    if fifo==None:
        if coluta.pOptions.no_connect:
            print('{} ->'.format(port),'DATA DATA DATA DATA')
            return True
        else:
            coluta.showError('SERIALMOD: Port {} not connected.'.format(port))
            return False

    # Create output array and reset the buffers
    outputArray = bytearray()

    # Block an unlocked thread before reading from chip
    # block = Thread.block()
    maxReadAttempts = 250
    nTries   = 0
    # print('nBytes',nBytes)
    # print('in_waiting ',fifo.in_waiting)
    
    if fifo.in_waiting==0:
        print('{} ->'.format(port),["{:02x}".format(x) for x in outputArray])
        return outputArray

    while len(outputArray) < nBytes:# and nTries<maxReadAttempts:
        # TODO? add breakout after timeout?
        nTries+=1
        output = fifo.read(fifo.in_waiting)
        # print(fifo.in_waiting)
        for b in output: 
            outputArray.append(b)
    # coluta.logger.addTraceback("{0} -> {1}".format(port," ".join(["{:02x}".format(x) for x in outputArray])))
    # If an unlocked thread was blocked, release the lock
    # Thread.block(block)

    if coluta.debug:
       print('{} ->'.format(port),["{:02x}".format(x) for x in outputArray])

    return outputArray

def flushBuffer(coluta):
    """ Flush the serial buffer to get rid of junk data"""
    fifo = coluta.serial
    if fifo is not None:
        fifo.reset_input_buffer()
        fifo.reset_output_buffer()
