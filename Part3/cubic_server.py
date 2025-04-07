
import socket
import time
import argparse
import json
import os
import matplotlib.pyplot as plt

# Constants
MSS = 1400  # Maximum Segment Size in bytes
TARGET_BANDWIDTH = 50 * 10**6  # Target bandwidth in bits per second

DUP_ACK_THRESHOLD = 3  # Threshold for duplicate ACKs to trigger fast recovery
timeout = 0.1  # Initial timeout value in seconds
timeout_val = 0.1
m_time = 0
u_check = False
m_seq_no = 0

# Congestion control variables
cwnd = MSS  # Congestion window, starting with 1 MSS
ssthresh = 64000*2  # Slow start threshold, initial arbitrary value

def estimate_rtt(server_socket, client_address):
    """
    Estimate initial RTT by sending multiple packets (with MSS-sized data) and taking the average of the times taken to receive ACKs.
    """
    rtt_samples = []
    test_data = '0' * MSS  # MSS-sized dummy data
    test_packet = json.dumps({"seq_num": 0, "data": test_data}).encode()  # Packet data with MSS size

    for i in range(10):
        # Send a test packet with MSS-sized data
        start_time = time.time()
        server_socket.sendto(test_packet, client_address)
        print(f"Sent test packet {i + 1} with MSS-sized data",flush=True)

        # Wait for the acknowledgment
        try:
            ack_packet, _ = server_socket.recvfrom(1024)
            end_time = time.time()
            rtt_samples.append(end_time - start_time)
            print(f"Received ACK for test packet {i + 1}, RTT = {rtt_samples[-1]:.6f} seconds",flush=True)
        except socket.timeout:
            print(f"Timeout waiting for ACK for test packet {i + 1}",flush=True)

    # Calculate average RTT, ignoring packets where timeout occurred
    avg_rtt = sum(rtt_samples) / len(rtt_samples) if rtt_samples else timeout
    print(f"Estimated initial RTT: {avg_rtt:.6f} seconds",flush=True)
    return avg_rtt

def calculate_window_size(avg_rtt):
    """
    Calculate the window size based on the target bandwidth, MSS, and estimated RTT.
    """
    window_size = ((TARGET_BANDWIDTH * avg_rtt) / (MSS * 8))  # Convert MSS to bits
    print(f"Calculated window size based on RTT: {window_size}",flush=True)
    print("window_size",window_size,flush=True)
    window_size = int(window_size)
    return max(1, window_size)  # Ensure at least a window size of 1

def send_file(server_ip, server_port, enable_fast_recovery):
    """
    Send a predefined file to the client, ensuring reliability over UDP.
    """
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind((server_ip, server_port))
    server_socket.settimeout(1000)
    print(f"Server listening on {server_ip}:{server_port}",flush=True)

    # # Wait for the client to initiate the connection
    file_path = "large_kurose.txt"

    #data, client_address = server_socket.recvfrom(1024)
    client_address=0
    connection_established = False

    while True:
        print("Waiting for client connection request...", flush=True)
        data, client_address = server_socket.recvfrom(1024)
        connection_data = json.loads(data.decode())
        connection_seq_num = connection_data['seq_num']
        if connection_seq_num == -2:
            print(f"Connection request received from client {client_address}", flush=True)
            break
    
    server_socket.settimeout(5)

    t1=0
    t2=0
    while True:
        try:
            t1=time.time()
            send_rtt(server_socket, client_address)
            ack_packet, _ = server_socket.recvfrom(1024)
            ack_data = json.loads(ack_packet.decode())
            seq_num = ack_data['seq_num']
            print("seq_num after sending rtt:",seq_num,flush=True)
            if seq_num != -1:
                continue
            t2=time.time()
            print("Received ack from client",flush=True)
            if t2-t1<1:
                break
            else:
                print(f"RTT({t2-t1} s) too high!!!\n\n",flush=True)
                continue                
        except socket.timeout:
            pass


    estimated_rtt=t2-t1
    print("estimated rtt: ",estimated_rtt,flush=True)
    # data, client_address = server_socket.recvfrom(1024)
    print(f"Connection established with client {client_address}",flush=True)

    # Initialize variables for throughput logging
    throughput_data = []
    time_data = []

    # Estimate initial RTT and set window size based on target bandwidth
    global timeout, m_time, m_seq_no, timeout_val, cwnd, ssthresh
    #estimated_rtt = estimate_rtt(server_socket, client_address)
    window = 6  # Adjust this value based on desired smoothing
    moving_avg = []
    dev_rtt = 0
    initial_time=time.time()
    timeout = estimated_rtt  # Use the initial estimated RTT for timeout
    timeout_val=timeout
    server_socket.settimeout(5*timeout)
    global_timeout=timeout
    window_size = calculate_window_size(estimated_rtt)
    cwnd = MSS #  $$$$
    fast_recovery_mode = False
    last_congestion_time = time.time()
    W_max = MSS  # Set W_max to current cwnd
    K = 0  # Calculate K
    last_sec=initial_time
    int_last_sec=0
    burst_data_sent = 0
    with open(file_path, 'r') as file:
        seq_num = 0
        unacked_packets = {}
        duplicate_ack_count = 0
        last_ack_received = -1
        u_check = False
        done = False
        while True:
            # Track data sent and time for each burst
            #burst_start_time = time.time()
            if time.time() - last_sec >= 0.5:
                last_sec+=0.5
                int_last_sec+=0.5
                instantaneous_throughput = burst_data_sent / (1e6)
                throughput_data.append(cwnd/1e5)
                time_data.append(int_last_sec)
                burst_data_sent=0
            # Send packets up to the window size
            count=0 
            while seq_num - last_ack_received < cwnd:
                chunk = file.read(MSS)
                if not chunk and len(unacked_packets) == 0:
                    # End of file
                    for i in range(10):
                        send_end_signal(server_socket, client_address)
                    done = True
                    break

                if not chunk:
                    break

                # Create and send the packet
                packet = create_packet(seq_num, chunk)
                if count == 0 and not u_check:
                    m_time=time.time()
                    m_seq_no = seq_num
                    u_check = True
                    print("Sending special packet",m_seq_no,flush=True)
                count+=1
                server_socket.sendto(packet, client_address)

                # Track data sent for throughput calculation
                burst_data_sent += len(chunk)
                # Add packet to unacked packets and track send time
                unacked_packets[seq_num] = (packet, time.time())
                print(f"Sent packet {seq_num}",flush=True)
                seq_num += len(chunk)
            if done:
                break
            # Handle ACKs and retransmissions
            try:
                print("Ready to receive",flush=True)
                server_socket.settimeout(timeout_val)  # Reset to current timeout
                ack_packet, _ = server_socket.recvfrom(1024)

                ack_data = json.loads(ack_packet.decode())
                ack_seq_num = ack_data['seq_num']
                if ack_seq_num < 0:
                    continue

                if cwnd >= ssthresh:
                    current_time = time.time()
                    T=current_time-last_congestion_time
                    cubic_wind = 0.5 * (T - K) ** 3 + W_max

                if ack_seq_num > last_ack_received:
                    duplicate_ack_count=0
                    print(f"Received cumulative ACK for packet {ack_seq_num}",flush=True)
                    if fast_recovery_mode:
                        cwnd = ssthresh
                        print("New Ack during Fast Recovery, cwnd:",cwnd,flush=True)
                        fast_recovery_mode = False
                    else:
                        # Congestion control: TCP Reno
                        if cwnd < ssthresh:
                            # Slow Start phase
                            cwnd += MSS
                            if cwnd>=ssthresh:
                                W_max = cwnd  # Set W_max to current cwnd
                                K = ((W_max * 0.5) / 0.4)**(1/3)  # Calculate K
                                print("from slow start to congestion avoidance: K",K,"W_max",W_max,flush=True)
                                last_congestion_time=time.time()
                            print("New Ack during Slow Start, cwnd:",cwnd,flush=True)
                        else:
                            # Congestion Avoidance phase
                            #cwnd += MSS*MSS//cwnd
                            cwnd=cubic_wind
                            print("T:",T,flush=True)
                            print("New Ack during Congestion Avoidance, cwnd:",cwnd,flush=True)

                    last_ack_received = ack_seq_num
                    print(last_ack_received,m_seq_no,u_check,flush=True)
                    timeout = estimated_rtt + 4 * dev_rtt
                    timeout_val = global_timeout


                    if ack_seq_num > m_seq_no and u_check:
                        t2 = time.time()
                        sample_rtt = t2 - m_time
                        print("sample rtt:",sample_rtt,flush=True)
                        alpha = 0.125
                        beta = 0.25
                        estimated_rtt = (1 - alpha) * estimated_rtt + alpha * sample_rtt
                        dev_rtt = (1 - beta) * (abs(sample_rtt - estimated_rtt)) + beta * abs(sample_rtt - estimated_rtt)
                        timeout = estimated_rtt + 4 * dev_rtt
                        print(f"Updated estimated RTT: {estimated_rtt:.6f} seconds, Timeout: {timeout_val:.6f} seconds",flush=True)
                        u_check = False
    
                    # Slide window forward and remove acknowledged packets
                    keys_to_remove = [k for k in unacked_packets if k < ack_seq_num]
                    for k in keys_to_remove:
                        del unacked_packets[k]

                elif seq_num == last_ack_received:
                    # Handle duplicate ACKs
                    if ack_seq_num == m_seq_no:
                        u_check = False
                    duplicate_ack_count += 1
                    print(f"Received duplicate ACK for packet {ack_seq_num}, count={duplicate_ack_count}",flush=True)
                    if fast_recovery_mode and enable_fast_recovery:
                        cwnd+=MSS
                        print("Fast Recovery and duplicate ack, cwnd:",cwnd,flush=True)
                    if enable_fast_recovery and duplicate_ack_count == DUP_ACK_THRESHOLD:
                        print("Entering fast recovery mode",flush=True)
                        # Fast retransmit and fast recovery
                        fast_recovery_mode = True
                        #ssthresh = cwnd // 2
                        cwnd = ssthresh + 3*MSS
                        W_max = cwnd  # Set W_max to current cwnd
                        K = ((W_max * 0.5) / 0.4)**(1/3)  # Calculate K
                        print("Entering fast recovery mode, cwnd:",cwnd," ssthresh:",ssthresh,flush=True)
                        fast_recovery(server_socket, client_address, unacked_packets, ack_seq_num)
                        #duplicate_ack_count = 0

            except socket.timeout:
                # Timeout: retransmit the oldest unacknowledged packet
                fast_recovery_mode = False
                W_max = cwnd  # Set W_max to current cwnd
                K = ((W_max * 0.5) / 0.4)**(1/3)  # Calculate K
                #ssthresh = cwnd // 2
                cwnd = MSS
                print("timeout occurred, cwnd",cwnd," ssthresh:",ssthresh,flush=True)
                u_check = False
                print("Timeout occurred, retransmitting unacknowledged packets",flush=True)
                timeout*=2
                timeout_val*=2
                print("New Timeout",timeout_val,flush=True)
                server_socket.settimeout(timeout_val)  # Set new timeout
                duplicate_ack_count=0
                retransmit_oldest_unacked_packets(server_socket, client_address, unacked_packets)

            # Calculate instantaneous throughput for this burst
            # burst_time = time.time() - burst_start_time
            # instantaneous_throughput = burst_data_sent / (burst_time * 1e6) # Bytes per second
            # if instantaneous_throughput > 0:
            #     throughput_data.append(instantaneous_throughput)
            #     time_data.append(time.time() - initial_time)  # Track time from start

            # Check if done sending the file
            # if not chunk and len(unacked_packets) == 0:
            #     print("File transfer complete",flush=True)
            #     break
    print("size of throughput_data:",len(throughput_data))
    # Iterate through the throughput list to calculate moving averages
    for i in range(len(throughput_data)):
        # Get the sublist for the current window, ensuring it doesn't exceed list bounds
        if i < window - 1:
            # For the initial points where there isn't enough data for the full window size
            window_ = throughput_data[:i + 1]
        else:
            # Use a fixed-size window
            window_ = throughput_data[i - window + 1:i + 1]
        # Compute the average of the current window
        window_sum = sum(window_)
        moving_avg.append(window_sum / len(window_))


    # Plotting throughput data
    plt.plot(time_data, moving_avg)
    plt.xlabel("Time (s)")
    plt.ylabel("Instantaneous Throughput (Mbps)")
    plt.title("Instantaneous Throughput Over Time")
    plt.savefig("Throughput_cubic.png")
    plt.show()
    
    

def create_packet(seq_num, data):
    """
    Create a packet with the sequence number and data in JSON format.
    """
    packet = json.dumps({"seq_num": seq_num, "data": data}).encode()
    return packet

def retransmit_oldest_unacked_packets(server_socket, client_address, unacked_packets):
    """
    Retransmit only the oldest unacknowledged packet.
    """
    if unacked_packets:
        # Find the oldest unacknowledged packet (smallest sequence number)
        oldest_seq_num = min(unacked_packets.keys())
        packet, _ = unacked_packets[oldest_seq_num]
        
        # Send the oldest unacknowledged packet
        server_socket.sendto(packet, client_address)
        print(f"Retransmitted oldest unacknowledged packet {oldest_seq_num}",flush=True)

def retransmit_all_unacked_packets(server_socket, client_address, unacked_packets):
    """
    Retransmit all unacknowledged packets.
    """
    if unacked_packets:
        for seq_num, (packet, _) in unacked_packets.items():
            # Send each unacknowledged packet
            server_socket.sendto(packet, client_address)
            print(f"Retransmitted unacknowledged packet {seq_num}", flush=True)

def fast_recovery(server_socket, client_address, unacked_packets, seq_num):
    """
    Fast retransmit the earliest unacknowledged packet.
    """
    if seq_num in unacked_packets:
        packet, _ = unacked_packets[seq_num]
        server_socket.sendto(packet, client_address)
        print(f"Fast recovery: retransmitted packet {seq_num}",flush=True)

def send_end_signal(server_socket, client_address):
    """
    Send an end-of-file signal to the client.
    """
    end_packet = json.dumps({"seq_num": -4, "data": ""}).encode()
    server_socket.sendto(end_packet, client_address)
    print("Sent END signal to client",flush=True)

def send_rtt(server_socket, client_address):

    rtt_packet = json.dumps({"seq_num": -3, "data": ""}).encode()
    server_socket.sendto(rtt_packet, client_address)
    print("Sent rtt to client",flush=True)

# Parse command-line arguments
parser = argparse.ArgumentParser(description='Reliable file transfer server over UDP.')
parser.add_argument('server_ip', help='IP address of the server')
parser.add_argument('server_port', type=int, help='Port number of the server')
#parser.add_argument('fast_recovery', type=lambda x: x.lower() == 'true', help='Enable fast recovery (true or false)')
args = parser.parse_args()

# Run the server
send_file(args.server_ip, args.server_port,True)
print("Server Done\n",flush=True)
