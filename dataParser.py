"""Module to parse output data. The data configuration is written by the user in a configuration file.
   An example configuration file is 'example_config.cfg'
   The module also writes the data to files. The names of the files are selected from the data types
   specified by the user.
name: dataParser.py
author: D.Panchal
email: dpanchal@utexas.edu
date: 8 August 2018"""


import configparser
import numpy
from collections import defaultdict
import os
import time
import csv
from glob import glob
from datetime import datetime
from ast import literal_eval
import h5py
from itertools import product

############# General helper function
def barrelRoll(dataList,order):
    """Naive implementation of a barrel shifter. Align the data bits using two consecutive samples"""
    # Number of 16-bit words in each measurement
    wordLength = 16
    
    if len(dataList)%wordLength!=0:
       print("Cannot align bits with an odd number of samples")
       return dataList

    # Chunk the 32-bit elements of dataList into groups of 16
    # Shift the samples by 16, i.e, one measurement 
    # This aligns the two consecutive subgroups 
    # For e.g., if we had coluta1 and coluta2 bits in dataList,
    # then we would align frame_coluta1_s[i] with frame_coluta1_s[i+1] in these two lists
    intialSampleList = [sample[i:i+wordLength] for sample in dataList for i in range(0,len(sample),wordLength)]
    nextSampleList = list(numpy.roll(intialSampleList,-16)) 
    
    # Loop through elements of the consecutive sample list to align the data bits
    barrelRolledList = []
    for s1,s2 in zip(intialSampleList,nextSampleList):
        # Join the LSByte of s[i] and MSByte of s[i+1]
        if order=='lsbmsb':
            serializedWord1 = s1[:8]+s2[8:]
            # serializedWord2 = s1[8:]+s2[:8]
        # Join the MSByte of s[i] and LSByte of s[i+1]
        elif order=='msblsb':
            serializedWord1 = s1[8:]+s2[:8]
            # serializedWord2 = s1[:8]+s2[8:]
        # Join the LSByte of s[i] and LSByte of s[i+1]
        elif order=='lsblsb':
            serializedWord1 = s1[:8]+s2[:8]
            # serializedWord2 = s1[8:]+s2[8:]
        # Join the MSByte of s[i] and MSByte of s[i+1]
        elif order=='msbmsb':
            serializedWord1 = s1[8:]+s2[8:]
            # serializedWord2 = s1[:8]+s2[:8] 

        barrelRolledList.append(serializedWord1)
        # barrelRolledList.append(serializedWord2)

    # Now make each element of the new list 32-bit long
    barrelRolledList = [barrelRolledList[i]+barrelRolledList[i+1] for i in range(0,len(barrelRolledList)-1)]
    return barrelRolledList

def isSequence(arg):
    """Determines if arg is a sequence. See https://stackoverflow.com/questions/1835018/"""
    return (not hasattr(arg, "strip") and
            (hasattr(arg, "__getitem__") or
             hasattr(arg, "__iter__")))

def stringRoll(words, shift):
    """Takes the list of strings that is our raw data (words) and rolls it.
    This is necessary when the data from the various COLUTA channels does not line up"""
    if not isSequence(words):
        print('stringRoll input is not an array')
        return words
    split_words = [list(word) for word in words]
    rolled_words = numpy.roll(split_words, shift)
    new_words = [''.join(rolled_word) for rolled_word in rolled_words]

    # You could do this in a one line list comp too:
    # new_words = [''.join(rolled_word) for rolled_word in numpy.roll([list(word) for word in words],shift)]

    return new_words


class dataParser():

    def __init__(self,coluta,configFile):
        """
        Init function reads the configuration file and creates dictionaries for each
        version of the data.
        """
        self.configFile = configFile
        self.output_directory = './data_files/'
        self.coluta = coluta

        # Updated config dict for comment annotation
        self.updatedConfigs = {}
        
        self.setupConfigurations()
        self.runNumber = 1
        self.outputDirectory = self.output_directory+'Run_'+str(self.runNumber).zfill(4)+'/'

        data_groups = self.general.getSetting('data_channels')
        for group in data_groups:
            setattr(self,group+'DecimalDict',defaultdict(list))
            setattr(self,group+'BinaryDict',defaultdict(list))
            for channel in getattr(self,group).getSetting('data_channels'):
                setattr(self,group+channel+'_fileNumber',0)

        # Check if the output directory exists, if not, create the directory
        while os.path.exists(self.outputDirectory):
            self.runNumber += 1
            self.outputDirectory = getattr(self,'output_directory')+'Run_'+str(self.runNumber).zfill(4)+'/'
        
        os.makedirs(self.outputDirectory)

    def setupConfigurations(self):
        """Set up the parser settings for each data source"""
        config = configparser.ConfigParser()
        config.optionxform=str

        if not os.path.isfile(self.configFile):
            self.coluta.showError('DATA PARSER: Configuration file not found')

        config.read(self.configFile)
        categoryDict = dict(config.items('Categories'))

        self.configurations = [] 
        for categoryName in categoryDict:
            categoryTemplate = categoryDict[categoryName]
            self.readConfigFile(categoryName,categoryTemplate)
            self.configurations.append(categoryName)

    def readConfigFile(self,categoryName,categoryTemplate):
        """Read sections of the config file"""
        config = configparser.ConfigParser()
        config.optionxform=str

        config.read(self.configFile)

        if not config.has_section(categoryTemplate):
            if not config.sections():
                self.coluta.showError('DATA PARSER: Error reading config file. No sections found')
            else:
                self.coluta.showError('DATA PARSER: Error reading {} section'.format(categoryTemplate))

        configItems = dict(config.items(categoryTemplate))
        setting = Setting(configItems)
        setattr(self,categoryName,setting) 

    def setHDF5Attributes(self,hdf5File,**kwargs):
        """Create and attach attributes specified in kwargs to the HDF5 group or dataset hdf5Object"""
        for key, value in kwargs.items():
            if isSequence(value):
                if type(value[0]) is str:
                    hdf5File.attrs.create(key,value,dtype=h5py.special_dtype(vlen=str))
                else:
                    hdf5File.attrs.create(key,value)
            else:
                if type(value) is str:
                    hdf5File.attrs.create(key,value,dtype=h5py.special_dtype(vlen=str))
                else:
                    hdf5File.attrs.create(key,value)

    def parseData(self,dTypetoParse,nSamplesToParse,dataFromChip):
        """Group input binary data into chunks and call relevant parser functions"""

        bitsPerMeasurement = int(self.general.getSetting('word_length'))
        dataChunks = [dataFromChip[i:i+bitsPerMeasurement] for i in range(0,len(dataFromChip),bitsPerMeasurement)]
        if dTypetoParse=='coluta':
            for group in self.general.getSetting('data_channels'):
                getattr(self,group+'BinaryDict').clear()
                getattr(self,group+'DecimalDict').clear()
            self.parseADC(dataChunks[:nSamplesToParse])
        elif dTypetoParse=='histogram':
            pass

    def parseADC(self,binaryData):
        """Parse and sort binary ADC data into data groups"""

        # Now we parse both the COLUTA chip data at once
        # Ask Jaro: Order of chips within one 256-bit word

        # Get the names of the data sources, i.e., coluta1,coluta2
        groups = self.general.getSetting('data_words')

        # Total bits for one measurement of data source 
        bitsPerSample = int(getattr(self,'rootGroup').settings['total_bits'])

        # Group the binaryList into 32-bit long words
        # Here I reverse the order to align them MSB->LSB. 
        # Chances are you might not need to reverse ...
        # dataSamples = [sample[i:i+bitsPerSample][::-1] for sample in binaryData for i in range(0,len(sample),bitsPerSample)]
        dataSamples = [sample[i:i+bitsPerSample] for sample in binaryData for i in range(0,len(sample),bitsPerSample)]
        # If the data need to be aligned, then uncomment this line
        # dataSamples = barrelRoll(dataSamples,order='msblsb')

        # The data from the lpGBT is packaged into 8 32-bit words called "groups"
        # In testboard v1.1, we are sending data in groups 1, 2, and 3 (groups are 0-indexed)
        # Within each group there are two channels. The mapping of where each channel is
        #  stored within each group is listed in dataConfig.cfg. This mapping can change
        #  between testboard revisions, but should be the same within a given revision
        for samples in zip(*[dataSamples[i::8] for i in range(8)]): # take all 8 lpGBT output words
            samples = samples[1:4] # but only keeps words 1, 2, and 3; where are data is
            # Verify that at least one sample isn't empty. May want to change all to any
            if all( sample=='0'*bitsPerSample for sample in samples ): continue
            # Loop over groups and their corresponding samples, and each channel within each group
            for (sample,group) in zip(samples,groups):
                # Get the parser settings
                configDict = getattr(self,group).settings
                # Get the names of the subgroups, e.g. frame, channel1
                dataChips = configDict['data_chips']
                dataChannels = configDict['data_channels']
                # Get the bit positions for the data subgroups
                lsbList = configDict['lsb']
                msbList = configDict['msb']
                # Take a 16-bit sample and store it in its proper channel list
                for (chip,channel,lsb,msb) in zip(dataChips,dataChannels,lsbList,msbList):
                    binaryDict = getattr(self,chip+'BinaryDict')
                    decodedWord = sample[int(lsb):int(msb)]
                    binaryDict[channel].append(decodedWord)

        # A problem with the alignment of the data coming from the COLUTAs to the lpGBT can arise
        # The misalignment for each channel is (currently) determined via trial and error, then
        #  stored in dataConfig.cfg as the "roll" attribute
        # This loop rolls the data for each channel so that they are all properly aligned
        for word in groups:
            configDict = getattr(self,word).settings
            dataChips = configDict['data_chips']
            dataChannels = configDict['data_channels']
            dataRoll = configDict['roll']
            for (chip,channel,roll) in zip(dataChips,dataChannels,dataRoll):
                binaryDict = getattr(self,chip+'BinaryDict')
                decimalDict = getattr(self,chip+'DecimalDict')
                binaryData = stringRoll(binaryDict[channel],int(roll))#[:-1]
                decimalData = [self.convertColutaBits(chip,channel,decodedWord) for decodedWord in binaryData]
                binaryDict[channel] = binaryData
                decimalDict[channel] = decimalData

    def parseHistogram(self,nSamplesToParse,binaryData):
        channelSettings = getattr(self,'histogram').settings
        dataChannels = channelSettings['data_channels']
        lsbList,msbList = channelSettings['lsb'],channelSettings['msb']
        nBytes = int(channelSettings['bytesPerBuffer'])

        dataSamples = [''.join(binaryData[i:i+nBytes][::-1]) for i in range(0,len(binaryData),nBytes)]
        uniqueDataSamples = list(set(dataSamples))
        binarySamples = {channelName:[] for channelName in dataChannels}
        decimalSamples = {channelName:[] for channelName in dataChannels}

        for sample in uniqueDataSamples:
            countMSB,valueMSB = int(msbList[0]),int(msbList[1])
            countLSB,valueLSB = int(lsbList[0]),int(lsbList[1])
            countDecoded = sample[countLSB:countMSB]
            valueDecoded = sample[valueLSB:valueMSB]
            if countDecoded=='' or valueDecoded=='': continue
            countDecimal = int(countDecoded,2)
            valueDecimal = int(valueDecoded,2)
            # get rid of zero bin number
            if countDecimal==0 or valueDecimal==0: continue
            binarySamples['bin_count'].append(countDecoded)
            binarySamples['bin_number'].append(valueDecoded)
            decimalSamples['bin_count'].append(countDecimal)
            decimalSamples['bin_number'].append(valueDecimal)
        
        return binarySamples,decimalSamples

    def getWeightsArray(self,group,channel,overflow=0):
        """gets the current ADC weights"""
        ch = channel[:2]+channel[-1]

        try:
            boxName = group+ch+'ArithmeticModeBox'
            measurementMode = getattr(self.coluta,boxName).currentText()
            calibration = (measurementMode.replace(' ','_')).lower()
            if overflow == 1 and calibration=='normal_mode':
                weights = [0,0,4095,0,0,0,0,0,0,0,0,0,0,0,0,0]
            else:
                weights = self.calibration.getSetting(calibration)

        except Exception:
            weights = self.calibration.getSetting('raw_data')

        weightsArr = numpy.array(weights,dtype=int)

        return weightsArr

    def convertColutaBits(self,group,channel,binaryWord):
        """Convert COLUTA bits based on calibration mode selected"""
        wordArr = numpy.array(list(map(int,binaryWord)))
        weightsArr = self.getWeightsArray(group,channel,overflow=wordArr[2])
        decimalWord = numpy.sum(numpy.dot(wordArr,weightsArr))

        return decimalWord
    
    def makeComments(self,**kwargs):
        """ 
        Make a string of comments to be put into each data file
        Format:
                Timestamp
                Config file path
                Updated settings different from the config file
                Comments from the comment box
        """
        # Create timestamp, default comment for all data files
        timestamp = 'Timestamp: {0}'.format(datetime.now().strftime("%y_%m_%d_%H_%M_%S.%f"))
        # Get the name of the config file
        # configFile = 'Config file: {0}'.format(getattr(self,'coluta').cfgFile)
        configFile = ' '
        # Get the comment box string
        commentBoxString = 'Comments: {0}'.format(getattr(self,'coluta').commentBox.toPlainText())

        # Get the list of updated settings 
        # updatedSetting = 'Updated settings: \n'
        # for key, value in self.updatedConfigs.items():
        #     updatedSetting  += str(key)+':'+str(value)+'\n'

        return '\n'.join([timestamp,configFile,commentBoxString])

    def writeDataToFile(self,writeHDF5File=False,writeCSVFile=False,**kwargs):
        """Write the data to its corresponding file"""        

        # commentString = self.makeComments(**kwargs)
        commentString = " "
        dynamicRanges = ['2mA', '5mA', '10mA']

        # Create filenames based on the data type 
        for group in self.general.getSetting('data_channels'):
            for channel in getattr(self,group).getSetting('data_channels'):

                fileNumber = getattr(self,group+channel+'_fileNumber')
                binaryData = getattr(self,group+'BinaryDict')
                decimalData = getattr(self,group+'DecimalDict')

                decimal_outFile = group.upper()+'_'+channel.upper()+'_'+str(fileNumber).zfill(4)+'_Decimal.txt'
                binary_outFile = group.upper()+'_'+channel.upper()+'_'+str(fileNumber).zfill(4)+'_Binary.txt'
                hdf5_outFile = 'Run_'+str(self.runNumber).zfill(4)+'_Output.hdf5'
                csv_outFile = group.upper()+'_'+channel.upper()+'_'+str(fileNumber).zfill(4)+'_Binary.csv'
                
                binaryFilePath  = os.path.join(self.outputDirectory,binary_outFile)
                decimalFilePath = os.path.join(self.outputDirectory,decimal_outFile)
                hdf5FilePath    = os.path.join(self.outputDirectory,hdf5_outFile)
                csvFilePath     = os.path.join(self.outputDirectory,csv_outFile)

                if self.coluta.debug:
                    numpy.savetxt(  binaryFilePath,
                                    binaryData[channel],
                                    fmt='%s',
                                    delimiter='\t',
                                    newline='\n',
                                    header=commentString)

                    numpy.savetxt(  decimalFilePath,
                                    decimalData[channel],
                                    fmt='%s',
                                    delimiter='\t',
                                    newline='\n',
                                    header=commentString)

                if writeCSVFile:
                    with open(csvFilePath, 'w', newline='\n') as csvfile:
                        writer = csv.writer(csvfile, delimiter=',')
                        writer.writerows(binaryData[channel])

                # frame isn't needed for analysis, so don't save it in hdf5
                if channel == 'frame': 
                    fileNumber += 1
                    setattr(self,group+channel+'_fileNumber',fileNumber)
                    continue

                if writeHDF5File:
                    dynamicRangeIdx = self.coluta.controlLAUROCDynamicRangeBox.currentIndex()

                    gainSelectBox = group+'ch'+channel[-1]+'GSBox'
                    manualSelectBox = group+'ch'+channel[-1]+'MSBox'
                    isGainSelect = getattr(self.coluta,gainSelectBox).isChecked()
                    isManualSelect = getattr(self.coluta,manualSelectBox).isChecked()
                    if not isManualSelect:
                        gain = 'AG'
                        gainNum = 0
                    elif isManualSelect and not isGainSelect:
                        gain = '4x'
                        gainNum = 1
                    elif isManualSelect and isGainSelect:
                        gain = '1x'
                        gainNum = 2

                    runMode = getattr(self.coluta,group+channel[:2]+channel[-1]+'ArithmeticModeBox').currentText()

                    # gain bit is now bit 4, not bit 2
                    if runMode == 'Raw Data':
                        decisionBits = numpy.array([int(sample[1]) for sample in binaryData[channel]]).astype(bool)
                    else: # only decision bit if runMode is normal_mode
                        decisionBits = numpy.array([int(sample[3]) for sample in binaryData[channel]]).astype(bool)

                    rawDataList = []
                    for sampleWord in binaryData[channel]:
                        tmpList = []
                        for sampleBit in sampleWord:
                            tmpList.append(int(sampleBit))
                        rawDataList.append(tmpList)
                    rawDataBits = numpy.array(rawDataList)

                    pulser_amp = int(self.coluta.controlSPIInstructionBox.toPlainText())
                    ### TO SAVE NEW ATTRIBUTES FOR CUTS, PUT THEM HERE, AND ONCE MORE LATER ###
                    rcS1 = self.coluta.lauroc1slowcontrolrcHGs1Box.toPlainText()
                    crS1 = self.coluta.lauroc1slowcontrolcrHGs1Box.toPlainText()
                    rcS2 = self.coluta.lauroc1slowcontrolrcHGs2Box.toPlainText()
                    hg_lg_c2 = self.coluta.lauroc1slowcontrolch1C2Box.toPlainText()
                    ONg20 = self.coluta.lauroc1slowcontrolbiasAmpliG20ONBox.isChecked()
                    SWIBOg20 = self.coluta.lauroc1slowcontrolbiasAmpliG20swiboBox.isChecked()
                    DACIBIg20 = self.coluta.lauroc1slowcontrolbiasAmpliG20dacIBIBox.toPlainText()
                    DAC_VDC_LG = self.coluta.lauroc1slowcontrolch1dacVdcLGBox.toPlainText() 
                    DAC_VDC_HG = self.coluta.lauroc1slowcontrolch1dacVdcHGBox.toPlainText()

                    with h5py.File(hdf5FilePath) as outFile:
                        measurement_group = outFile.require_group('Measurement_'+str(fileNumber)) # create group if it doesn't already exist
                        adc_subgroup = measurement_group.require_group(group)
                        channel_subgroup = adc_subgroup.create_group(channel)
                        channel_subgroup.create_dataset('raw_data',data=rawDataBits,dtype='int8',compression='gzip')
                        if self.coluta.debug:
                            channel_subgroup.create_dataset('samples',data=decimalData[channel])
                            channel_subgroup.create_dataset('bits',data=decisionBits) # save decision bits as booleans
                        if 'n_adcs' not in outFile.attrs:
                            self.setHDF5Attributes( outFile, # will make all these values correct/editable when pulser is implemented
                                                    n_adcs=2,
                                                    adc_freq=self.coluta.frequency,
                                                    serial_number = self.coluta.serial_number)
                                                    # chip_number=self.coluta.boardConfigFileBox.currentText(),
                                                    # config_file=self.coluta.configFileNameBox.toPlainText()
                        # Save the SAR weights for each channel once per run 
                        if f'{group}_{channel}_SAR_weights' not in outFile.attrs:
                            self.setHDF5Attributes( outFile, 
                                                    **{f'{group}_{channel}_SAR_weights': self.getWeightsArray(group,channel)})

                        if 'run_type' not in measurement_group.attrs:
                            try:
                                dc_offset=self.coluta.function_generator.getSetting('offset')
                            except Exception:
                                dc_offset = 0.0
                            self.setHDF5Attributes( measurement_group,
                                                    run_type=self.coluta.runType,
                                                    laurocDynamicRange=dynamicRanges[dynamicRangeIdx],
                                                    dc_offset=dc_offset,
                                                    n_samples = self.coluta.nSamples,
                                                    awg_freq = self.coluta.awgFreq,
                                                    pulse_length = self.coluta.pulseLength,
                                                    pulser_amp = pulser_amp,
                                                    ### ALSO PUT NEW ATTRIBUTES HERE TO SAVE THEM ###
                                                    # shaper_constants = rcS1+'_'+crS1+'_'+rcS2,
                                                    # hg_lg_c2 = hg_lg_c2,
                                                    # on_g20 = ONg20,
                                                    # sw_ibo_g20 = SWIBOg20,
                                                    # dac_ibi_g20 = DACIBIg20,
                                                    dac_vdc_lg = DAC_VDC_LG,
                                                    dac_vdc_hg = DAC_VDC_HG)
                            if self.coluta.debug:
                                self.setHDF5Attributes(measurement_group, timestamp=self.coluta.measurementTime)
                            if self.coluta.runType == 'pulse': # probably not the best way to check this
                                attributes = self.pulseRun.settings
                            elif self.coluta.runType == 'sine':
                                attributes = self.sineRun.settings
                            elif self.coluta.runType == 'ramp':
                                attributes = self.rampRun.settings
                            elif self.coluta.runType == 'pedestal' or self.coluta.runType == 'onboard':
                                attributes = None
                            if attributes: self.setHDF5Attributes(measurement_group, **attributes)

                        if 'channels' not in adc_subgroup.attrs:
                            self.setHDF5Attributes( adc_subgroup,
                                                    channels = getattr(self,group).getSetting('data_channels'))

                        laurocGain = getattr(self,group).getSetting('laurocGain')[int(channel[-1])-1]
                        self.setHDF5Attributes( channel_subgroup,
                                                gain=gainNum,
                                                run_mode = runMode,
                                                laurocGain=laurocGain)
                        self.setHDF5Attributes( outFile,
                                                n_measurements = fileNumber+1)


                fileNumber += 1
                setattr(self,group+channel+'_fileNumber',fileNumber)


class Setting:
    def __init__(self,configDict):
        self.settings = {}
        for name,value in configDict.items():
            settingValue = value.split(',')
            if len(settingValue)>1:
                self.settings[name] = settingValue
            else:
                self.settings[name] = settingValue[0]

    
    def getSetting(self,settingName):
        try:
            value = self.settings[settingName]
        except KeyError:
            print('Key Error: The device does not have the setting ' +settingName)

        return value

    def setSetting(self,settingName,settingValue):
        try:
            self.settings[settingName] = settingValue
            self.updated = True
        except KeyError:
            print('Cannot update setting')