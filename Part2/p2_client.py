
import socket
import argparse
import json
import time

# Constants
MSS = 1400  # Maximum Segment Size

def receive_file(server_ip, server_port, a):
    """
    Receive the file from the server with reliability, handling packet loss and reordering.
    """
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client_socket.settimeout(5)  # Set timeout for server response

    server_address = (server_ip, server_port)
    expected_seq_num = 0
    output_file_path = a+"received_file.txt"
    out_of_order_buffer = {}  # Buffer for out-of-order packets

    # Send connection request 10 times
    # for attempt in range(10):
    #     connection_request = "CONNECTION_REQUEST"
    #     client_socket.sendto(connection_request.encode(), server_address)
    #     print(f"Connection request sent to server (Attempt {attempt + 1}/10)")
    #     time.sleep(0.005)  # Wait 1 second before sending the next request

    while True:
        try:
            connection_request = json.dumps({"seq_num": -2}).encode()
            client_socket.sendto(connection_request, server_address)
            print(f"Connection request sent to server",flush=True)
            packet, _ = client_socket.recvfrom(MSS + 4000)
            print("received first rtt from server",flush=True)
            send_ack(client_socket, server_address, -1)
            break
        except socket.timeout:
            pass


    with open(output_file_path, 'w'):
        pass
    cnt_data_pkt=0
    with open(output_file_path, 'a') as file:
        while True:
            try:
                # Receive the packet from the server
                packet, _ = client_socket.recvfrom(MSS + 4000)  # Allow room for headers
                #print(31,flush=True)
                packet_data = json.loads(packet.decode())
                seq_num = packet_data['seq_num']
                data = packet_data['data']

                if seq_num==-4:
                    print("Received END signal from server, file transfer complete",flush=True)
                    break
                
                if cnt_data_pkt<20 and seq_num==-3:
                    print("Received RTT again from server",flush=True)
                    send_ack(client_socket, server_address, -1)
                    print("Sent ack again to server",flush=True)
                    continue
                else:
                    cnt_data_pkt+=1
                # Deserialize packet using JSON
                
                
                #data = packet_data['data'].encode()
                #print("data:",data)
                # Check for end of file signal

                #print(48,flush=True)

                # Handle in-order packet
                #print(seq_num,expected_seq_num)
                if seq_num == expected_seq_num:
                    test_data = '0' * MSS
                    if data == test_data:
                        send_ack(client_socket, server_address, 0)
                        continue
                    #print(data)
                    file.write(data)
                    print(f"Received in-order packet {seq_num}, writing to file",flush=True)
                    expected_seq_num += len(data)

                    # Write any buffered packets in order
                    while expected_seq_num in out_of_order_buffer:
                        next_data = out_of_order_buffer.pop(expected_seq_num)
                        file.write(next_data)
                        print(f"Writing buffered packet {expected_seq_num} to file",flush=True)
                        expected_seq_num += len(next_data)

                    # Send cumulative ACK for the highest contiguous packet received
                    send_ack(client_socket, server_address, expected_seq_num)
                elif seq_num > expected_seq_num:
                    # Out-of-order packet, store in buffer
                    out_of_order_buffer[seq_num] = data
                    print(f"Buffered out-of-order packet {seq_num}, expecting {expected_seq_num}",flush=True)
                
                    # Send cumulative ACK for the last in-order packet received
                    send_ack(client_socket, server_address, expected_seq_num)
                
                else:
                    send_ack(client_socket, server_address, expected_seq_num)


            except socket.timeout:
                print("Timeout waiting for data from server",flush=True)

    client_socket.close()

def send_ack(client_socket, server_address, seq_num):
    """
    Send a cumulative acknowledgment for the received packet.
    """
    ack_packet = json.dumps({"seq_num": seq_num}).encode()
    client_socket.sendto(ack_packet, server_address)
    print(f"Sent cumulative ACK for packet {seq_num}",flush=True)

# Parse command-line arguments
parser = argparse.ArgumentParser(description='Reliable file receiver over UDP.')
parser.add_argument('server_ip', help='IP address of the server')
parser.add_argument('server_port', type=int, help='Port number of the server')
parser.add_argument('--pref_outfile', default='', help='Prefix for the output file')
args = parser.parse_args()

# Run the client
result = receive_file(args.server_ip, args.server_port, args.pref_outfile)
print("Client Done\n",flush=True)

