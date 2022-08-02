import numpy as np
import math
from scipy.signal import lfilter
import matplotlib.pyplot as plt

##Generates a physics pulse. data1 is the raw pulse, data2 is the filtered/shaped pulse

ext_freq = 1200e6  # arbitrary waveform generator frequency
sim = float(1 / ext_freq)  # simulation time resolution
rise = 2.4e-9  # rise time
width = 400e-9  # width of pulse
period = float(1600e-9 - 1 * sim)  # total length of signal
amp = 1  # amplitude of signal
delay = 10*sim # 0e-9
tau = 21.5e-9  # RC time constant
time1 = np.linspace(0, period, math.floor(period / sim))  # time array
pulse = np.zeros(len(time1))

# Form signal wave
i = 0
for t in time1:
    if t < rise + delay and t > delay:
        pulse[i] = amp * (t - delay) / rise  # rising ramp
    elif t < width + delay and t > delay:
        pulse[i] = amp * (width - t + delay) / (width - rise)  # falling ramp
    else:
        pulse[i] = 0  # zeros elsewhere
    i += 1
# print(pulse[0:10])
# Filtering parameters
## lfilter is a rational transfer function filter described here:
##      https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.lfilter.html
d = 2 * tau / sim  # bilinear transform from laplace to z
c = d / ((1 + d) ** 3)
f = (1 - d) / (1 + d)
b_old = [1, 1, -1, -1]
b = [c * j for j in b_old]  # transfer function numerator
a = [1, 3 * f, 3 * f ** 2, f ** 3]  # transfer function denominator

filtered_pulse = lfilter(b, a, pulse)

#######################################
## Convert to Bytes

data1 = -1*filtered_pulse
data2 = -1*pulse
SampleNum = len(data1)
byteSamples = bytearray(2 * SampleNum)  # declare the array of bytes

min1 = min(data1);  # check for negative mins -> shift 0 to eliminate
if min1 > 0:  # if min is pos, no need to shift data
    min1 = 0

min2 = min(data2);  # check for negative mins -> shift 0 to eliminate
if min2 > 0:  # if min is pos, no need to shift data
    min2 = 0

# Convert to bytes

i = 0
for d in data1: # shaped (LAr) pulse
    # Func=i;
    Func = (d + abs(min1)) * 8191  # shift to avoid negatives, 8191 scales so waveform appears on screen

    byteSamples[2 * i] = (int)(Func / 256)  # upper

    byteSamples[2 * i + 1] = (int)(Func % 256)  # lower

    i += 1

data3 = np.array([])
for iRep in range(1):
    data3 = np.append(data3,data2)
data2 = data3

byteSamples2 = bytearray(2 * len(data2))  # declare the array of bytes
i = 0
for d in data2: # physics (triangular) pulse
    # Func=i;
    Func = (d+abs(min2)) * 8191  # 8191 scales so waveform appears on screen

    byteSamples2[2 * i] = (int)(Func / 256)  # upper

    byteSamples2[2 * i + 1] = (int)(Func % 256)  # lower

    i += 1

if __name__ == "__main__":
    plt.subplot(2, 1, 1)
    plt.plot(time1, data1)
    plt.subplot(2, 1, 2)
    # plt.plot(time1, data2)
    plt.plot(data2)
    plt.show()
