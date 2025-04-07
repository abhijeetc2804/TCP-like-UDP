
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.link import TCLink
from mininet.node import RemoteController
from mininet.log import setLogLevel
import time, os, sys, hashlib, math
import matplotlib.pyplot as plt

class CustomTopo(Topo):
    def build(self, loss, delay):
        # Add two hosts
        h1 = self.addHost('h1')
        h2 = self.addHost('h2')

        # Add a single switch
        s1 = self.addSwitch('s1')

        # Add links
        # Link between h1 and s1 with specified packet loss and delay
        self.addLink(h1, s1, loss=loss, delay=f'{delay}ms')
        # Link between h2 and s1 with no packet loss or delay
        self.addLink(h2, s1, loss=0)

def compute_md5(file_path):
    """Compute the MD5 hash of a file."""
    hasher = hashlib.md5()
    try:
        with open(file_path, 'rb') as file:
            while chunk := file.read(8192):
                hasher.update(chunk)
        return hasher.hexdigest()
    except FileNotFoundError:
        print(f"File not found: {file_path}")
        return None

def run_experiment(expname):
    # Set the log level to info to see detailed output
    setLogLevel('info')

    # Controller IP and port (adjust if needed)
    controller_ip = '127.0.0.1'
    controller_port = 6653

    # Output file for results
    output_file = f'reliability_{expname}.csv'
    with open(output_file, 'w') as f_out:
        f_out.write("loss,delay,fast_recovery,md5_hash,ttc\n")

        SERVER_IP = "10.0.0.1"
        SERVER_PORT = 6555
        NUM_ITERATIONS = 1
        OUTFILE = 'received_file.txt'

        # Define the loss and delay lists based on experiment type
        delay_list, loss_list = [], []
        if expname == "loss":
            loss_list = [x * 0.5 for x in range(0, 11)]
            # loss_list = [0.5]
            delay_list = [20]
        elif expname == "delay":
            delay_list = [x for x in range(0, 201, 20)]
            loss_list = [1]
        print("Loss List:", loss_list, "Delay List:", delay_list)

        # Experiment loop
        for LOSS in loss_list:
            for DELAY in delay_list:
                for FAST_RECOVERY in [True]:
                    avg=0
                    for i in range(NUM_ITERATIONS):
                        print(f"\n--- Running topology with {LOSS}% packet loss, {DELAY}ms delay and fast recovery {FAST_RECOVERY}")

                        # Create the custom topology
                        topo = CustomTopo(loss=LOSS, delay=DELAY)
                        net = Mininet(topo=topo, link=TCLink, controller=None)
                        remote_controller = RemoteController('c0', ip=controller_ip, port=controller_port)
                        net.addController(remote_controller)
                        net.start()

                        # Get host references
                        h1, h2 = net.get('h1'), net.get('h2')

                        # Ensure 
                        # Logs directory exists
                        if not os.path.exists('./Logs'):
                            os.makedirs('./Logs')

                        # Run the server and client programs
                        start_time = time.time()
                        print(87)
                        h1.cmd(f"python3 cubic_server.py {SERVER_IP} {SERVER_PORT} > ./server_output.log 2>&1 &")
                        result = h2.cmd(f"python3 p2_client.py {SERVER_IP} {SERVER_PORT} > ./client_output.log 2>&1")
                        print("result:[",result,"]")
                        end_time = time.time()
                        ttc = end_time - start_time
                        print(92)
                        # Compute MD5 hash of the received file
                        md5_hash = compute_md5(OUTFILE)
                        avg+=ttc
                        # Write results to file
                        print(f"{LOSS},{DELAY},{FAST_RECOVERY},{md5_hash},{ttc}\n")
                        # Stop the network
                        net.stop()

                        # Cleanup the received file for next iteration
                        if os.path.exists(OUTFILE):
                            os.remove(OUTFILE)
                        time.sleep(1)
                    avg/=NUM_ITERATIONS
                    f_out.write(f"{LOSS},{DELAY},{FAST_RECOVERY},{md5_hash},{avg}\n")
                    print(f"Average Value: {LOSS},{DELAY},{FAST_RECOVERY},{md5_hash},{avg}\n")

    print("\n--- Completed all tests ---")
    return output_file

def plot_results(expname, output_file, file_size):
    # Initialize data lists
    loss_data, delay_data = [], []
    ttc_with_fr, ttc_without_fr = [], []
    throughput_loss_plot, throughput_delay_plot = [], []  # Additional lists for throughput plots
    _RTT=0
    # Read CSV data
    with open(output_file, 'r') as f:
        next(f)  # Skip header
        for line in f:
            loss, delay, fast_recovery, _, ttc = line.strip().split(',')
            ttc = float(ttc)
            if float(loss)<0.001 or float(delay)<0.001:
                continue
            if expname == "loss":
                p = float(loss) / 100  # Convert packet loss percentage to a probability
                if fast_recovery == "True":
                    loss_data.append(float(loss))
                    ttc_with_fr.append(file_size/ttc)
                    throughput = file_size / ttc
                    throughput_loss_plot.append(throughput * math.sqrt(p))
                else:
                    ttc_without_fr.append(ttc)
            elif expname == "delay":
                delay_ms = float(delay)
                if fast_recovery == "True":
                    _RTT=2*delay_ms
                    delay_data.append(delay_ms)
                    ttc_with_fr.append(file_size/ttc)
                    throughput = file_size / ttc
                    throughput_delay_plot.append(throughput * _RTT if _RTT else throughput)
                else:
                    ttc_without_fr.append(file_size/ttc)

    # Plot Transmission Time (TTC) based on experiment type
    if expname == "loss":
        plt.figure(figsize=(10, 6))
        plt.plot(loss_data, ttc_with_fr, marker='x', color='blue')
        plt.xlabel('Packet Loss (%)')
        plt.ylabel('Average Throughput(Kbps)')
        plt.title('Average Throughput vs Packet Loss')
        plt.grid()
        plt.savefig('loss_throughput.png')
        plt.show()

        # Separate plot for Throughput * sqrt(p)
        plt.figure(figsize=(10, 6))
        plt.plot(loss_data, throughput_loss_plot, marker='o', color='red')
        plt.xlabel('Packet Loss (%)')
        plt.ylabel('Throughput * sqrt(p)')
        plt.title('Throughput Adjustment vs Packet Loss')
        plt.grid()
        plt.ylim(0, None)
        plt.savefig('loss_throughput_adjustment.png')
        plt.show()

    elif expname == "delay":
        plt.figure(figsize=(10, 6))
        plt.plot(delay_data, ttc_with_fr, marker='x', color='blue')
        plt.xlabel('Network Delay (ms)')
        plt.ylabel('Average Throughput(Kbps)')
        plt.title('Average Throughput vs Network Delay')
        plt.grid()
        plt.savefig('delay_throughput.png')
        plt.show()

        # Separate plot for Throughput * RTT
        plt.figure(figsize=(10, 6))
        plt.plot(delay_data, throughput_delay_plot, marker='o', color='red')
        plt.xlabel('Network Delay (ms)')
        plt.ylabel('Throughput * RTT')
        plt.title('Throughput Adjustment vs Network Delay')
        plt.grid()
        plt.ylim(0, None)
        plt.savefig('delay_throughput_adjustment.png')
        plt.show()
    else:
        print("Invalid experiment name. Use 'loss' or 'delay'.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python experiment.py <expname>")
    else:
        expname = sys.argv[1].lower()
        output_file = f'reliability_{expname}1.csv'
        # output_file = run_experiment(expname)
        file_size = os.path.getsize("kurose.txt")
        file_size/=1000 # file size in Kb
        print("file_size: ",file_size)
        plot_results(expname, output_file, file_size)