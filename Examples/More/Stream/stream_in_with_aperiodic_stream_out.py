"""
Demonstrates usage of aperiodic stream-out functions with stream-in

Streams in while streaming out arbitrary values. These arbitrary stream-out
values act on DAC0 to cyclically increase the voltage from 0 to 2.5.
Though these values are generated before the stream starts, the values could
be dynamically generated, read from a file, etc.

Relevant Documentation:
 
LJM Library:
    LJM Library Installer:
        https://labjack.com/support/software/installers/ljm
    LJM Users Guide:
        https://labjack.com/support/software/api/ljm
    Opening and Closing:
        https://labjack.com/support/software/api/ljm/function-reference/opening-and-closing
    LJM Single Value Functions (like eReadName, eReadAddress): 
        https://labjack.com/support/software/api/ljm/function-reference/single-value-functions
    Stream Functions (eStreamRead, eStreamStart, etc.):
        https://labjack.com/support/software/api/ljm/function-reference/stream-functions
 
T-Series and I/O:
    Modbus Map:
        https://labjack.com/support/software/api/modbus/modbus-map
    Stream Mode:
        https://labjack.com/support/datasheets/t-series/communication/stream-mode
    Analog Inputs:
        https://labjack.com/support/datasheets/t-series/ain
    Stream-Out:
        https://labjack.com/support/datasheets/t-series/communication/stream-mode/stream-out/stream-out-description
    Digital I/O:
        https://labjack.com/support/datasheets/t-series/digital-io
    DAC:
        https://labjack.com/support/datasheets/t-series/dac

"""
import sys

from time import sleep

from labjack import ljm

import ljm_stream_util


# Setup

IN_NAMES = ["AIN0"]

"""
STREAM_OUTS = [
    {
        "target": str register name that stream-out write_data will be sent to,

        "index": int STREAM_OUT# offset. 0 would generate names like
            "STREAM_OUT0_BUFFER_STATUS", etc.
    },
    ...
]
"""
STREAM_OUTS = [
    {
        "target": 1000, #DAC0
        "index": 0
    }#,
    # {
    #     "target": 1002, #DAC1
    #     "index": 1
    # }
]

INITIAL_SCAN_RATE_HZ = 1000
NUM_WRITES = 8
SAMPLES_TO_WRITE = 512


def print_register_value(handle, register_name):
    value = ljm.eReadName(handle, register_name)
    print("%s = %f" % (register_name, value))


def open_ljm_device(device_type, connection_type, identifier):
    try:
        handle = ljm.open(device_type, connection_type, identifier)
    except ljm.LJMError:
        print(
            "Error calling ljm.open(" +
            "device_type=" + str(device_type) + ", " +
            "connection_type=" + str(connection_type) + ", " +
            "identifier=" + identifier + ")"
        )
        raise

    return handle

def print_device_info(handle):
    info = ljm.getHandleInfo(handle)
    print(
        "Opened a LabJack with Device type: %i, Connection type: %i,\n"
        "Serial number: %i, IP address: %s, Port: %i,\nMax bytes per MB: %i\n" %
        (info[0], info[1], info[2], ljm.numberToIP(info[3]), info[4], info[5])
    )

def make_scan_list(in_names, stream_outs):
    """Creates a list of integer addresses from lists of in and out names."""
    in_addresses = []
    out_addresses = []

    if in_names:
        in_addresses = ljm_stream_util.convert_names_to_addresses(in_names)
    for stream_out in stream_outs:
        out_addresses.append(4800+stream_out["index"])

    return in_addresses + out_addresses

def main(
    initial_scan_rate_hz=INITIAL_SCAN_RATE_HZ,
    in_names=IN_NAMES,
    stream_outs=STREAM_OUTS,
    num_cycles=NUM_WRITES
):
    print("Beginning...")
    handle = open_ljm_device(ljm.constants.dtANY, ljm.constants.ctANY, "ANY")
    print_device_info(handle)

    write_data = []
    for i in range(SAMPLES_TO_WRITE):
        sample = 2.5*i/SAMPLES_TO_WRITE
        write_data.append(sample)
    scans_per_read = int(initial_scan_rate_hz / 2)

    try:
        print("Initializing stream out buffers...")
        for stream_out in stream_outs:
            ljm.initializeAperiodicStreamOut(handle, stream_out["index"], stream_out["target"], initial_scan_rate_hz)
            # Write some data to the buffer before the stream starts
            ljm.writeAperiodicStreamOut(handle, stream_out["index"], SAMPLES_TO_WRITE, write_data)
            ljm.writeAperiodicStreamOut(handle, stream_out["index"], SAMPLES_TO_WRITE, write_data)
        print("")
        scan_list = make_scan_list(
            in_names=in_names,
            stream_outs = stream_outs
        )
        print("scan_list: " + str(scan_list))
        print("scans_per_read: " + str(scans_per_read))
        scan_rate = ljm.eStreamStart(handle, scans_per_read, len(scan_list),
                                     scan_list, initial_scan_rate_hz)
        start_time = ljm.getHostTick();
        print("\nStream started with a scan rate of %0.0f Hz." % scan_rate)
        print("\nPerforming %i buffer updates." % num_cycles)
        iteration = 0
        total_num_skipped_scans = 0
        while iteration < num_cycles:
            for stream_out in stream_outs:
                ljm.writeAperiodicStreamOut(handle, stream_out["index"], SAMPLES_TO_WRITE, write_data)
            # ljm.eStreamRead will sleep until data has arrived
            stream_read = ljm.eStreamRead(handle)
            num_skipped_scans = ljm_stream_util.process_stream_results(
                iteration,
                stream_read,
                in_names
            )
            total_num_skipped_scans += num_skipped_scans
            iteration = iteration + 1
        # Since scan rate determines how quickly data can be written from the device
        # large chunks of data written at low scan rates can take longer to write
        # out than it takes to call LJM_WriteAperiodicStreamOut and 
        # LJM_eStreamRead. some delay may be necessary if it is desired to write out
        # all data then immediately close the stream
        run_time = (ljm.getHostTick() - start_time)/1000;
        # 512 samples * 10 writes = 5120 samples. scan rate = 1000
        # samples/sec, so it should take 5.12 seconds to write all data out
        stream_out_ms = 1000 * SAMPLES_TO_WRITE * (NUM_WRITES + 2) / scan_rate;
        if (run_time < stream_out_ms):
            sleep((stream_out_ms - run_time)/1000)

    except ljm.LJMError:
        ljm_stream_util.prepare_for_exit(handle)
        raise
    except Exception:
        ljm_stream_util.prepare_for_exit(handle)
        raise

    ljm_stream_util.prepare_for_exit(handle)
    print("Total number of skipped scans: %d" % total_num_skipped_scans)

if __name__ == "__main__":
    main()
