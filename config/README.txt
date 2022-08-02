#################### Configuration Files for Control Bits ####################

This file follows a very strict syntax. Configuration type is the setting name
in [square brackets]. Immediately following should be the total number of bits
expected. Then, each the configuration bits are listed in the form
    
    setting1: value1
    setting2: value2
    ...

The number of spaces between the colon and the value is ignored. The order of
the settings is important, as this is the order in which the settings will be
concetenated and sent to the chip. DO NOT MANUALLY EDIT CONFIG FILES UNLESS YOU
KNOW WHAT YOU ARE DOING.

Comments begin with the '#' symbol and can be placed anywhere. The name of the
config file can be a comment on the first line.



####################### Configuration Files for Parsing #######################

This file will be follow a strict syntax. 
Configuration type is the version number of the chip data. 
Immediately following should be the chip name and the data sequence. For example,

	[version number]
	chip_name: value
	data_sequence: arrangement of the data types in a data word arranged 
	               from the MSB to the LSB

Following these two configurations, the next two entries are 'coluta_word' 
and 'regroup_words'. The setting 'coluta_word' contains the data types which 
make up the coluta channel (SAR+DRE). The setting 'regroup_words' contains the
data types which need to be regrouped into a different length (default: 8 bits).
The follwing set of entries denote the number of bits for each data type. 
Since the data type COLUTA contains DRE and SAR, the user should define 
the number of bits for DRE and SAR.

The number of spaces between the colon and the value is ignored. 

DO NOT MANUALLY EDIT CONFIG FILES UNLESS YOU KNOW WHAT YOU ARE DOING.

Comments begin with the '#' symbol and can be places anywhere. The name of the 
config file can be a comment on the first line.

