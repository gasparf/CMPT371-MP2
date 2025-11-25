# Include Python's Socket Library
from socket import *
from prtp_packet import PRTPPacket
import sys
import time

class GoBackNReceiver:
    # Go-Back-N Receiver with 3-way handshake and Flow Control
    # - Connection establishment (SYN -> SYN-ACK -> ACK)
    # - Receives packets in order
    # - Sends cumulative ACKs with advertised window
    # - Discards out-of-order packets (Go-Back-N behavior)
    # - Checksum validation for all packets
    
    def __init__(self, port):
        # intialize the receiver
        # Args:
        # port: Local port to bind to
        
        self.socket = socket(AF_INET, SOCK_DGRAM)
        self.socket.bind(('', port))
        self.socket.settimeout(30.0)  # Set timeout for connection establishment
        
        # connection state
        self.connected = False
        self.client_addr = None
        self.seq_num = 0
        self.expected_seq = 0
        
        # flow control parameters
        self.MAX_BUFFER_SIZE = 65535  # Maximum buffer size
        self.received_data = b''  # Buffer for received data
        self.available_buffer = self.MAX_BUFFER_SIZE

        print(f"[RECEIVER] Initialized on port: {port}")
        
    def listen(self):
        # wait for incoming connections for 3-way handshake for PRTP requirements
        # Returns:
        # True if connection established, False otherwise
        
        print("[HANDSHAKE] Waiting for connection...")
        
            # Wait for SYN packet
        try:
            while True:
                data, addr = self.socket.recvfrom(PRTPPacket.MAX_PACKET_SIZE)
                syn_packet = PRTPPacket.deserialize(data) # validate checksum here through deseralize
                    
                if syn_packet and syn_packet.has_flag(PRTPPacket.FLAG_SYN):
                    print(f"[HANDSHAKE] Received SYN from {addr}, seq={syn_packet.seq_num}")
                    self.client_addr = addr
                        
                    # Send SYN-ACK
                    self.seq_num = 0
                    syn_ack_packet = PRTPPacket(
                        seq_num=self.seq_num,
                        ack_num=syn_packet.seq_num+1,
                        window_size=self.available_buffer,
                        flags=PRTPPacket.FLAG_SYN | PRTPPacket.FLAG_ACK
                    )
                    self.socket.sendto(syn_ack_packet.serialize(), self.client_addr)
                    print(f"[HANDSHAKE] Sent SYN-ACK, seq={self.seq_num}, ack={syn_packet.seq_num+1}")
                        
                    # Wait for ACK packet
                    data, addr = self.socket.recvfrom(PRTPPacket.MAX_PACKET_SIZE)
                    ack_packet = PRTPPacket.deserialize(data)
                        
                    if ack_packet and ack_packet.has_flag(PRTPPacket.FLAG_ACK):
                        print(f"[HANDSHAKE] Received ACK, seq={ack_packet.seq_num}, ack={ack_packet.ack_num}")
                        self.expected_seq = ack_packet.ack_num # Next expected seq num from sender
                        self.connected = True
                            
                        print("[HANDSHAKE] Connection established!")
                        print("[RECEIVER] Ready to receive data. Flow control window size:", self.available_buffer)
                        return True
                    else:
                        print("[HANDSHAKE] Invalid ACK packet, waiting for new SYN")
                        continue
        except timeout:
                print("[HANDSHAKE] Timeout waiting for SYN, retrying...")
                return False
        except Exception as e:
                print(f"[HANDSHAKE] Error: {e}")
                return False
            


    def handle_incoming_frame(seq, data, send_ack):
        global EXPECTED_SEQ

        

        if seq == EXPECTED_SEQ: #correct sequence number, process packet
            print("Received new packet:", data) #frame is the raw incoming "packet" you received, already decoded to Python dict of "{"seq": 3, "data": "hello"}""

            # Process packet normally

            # Send ACK
            msg = send_ack(seq) +  data.upper() 

            EXPECTED_SEQ += 1      # Next expected packet, not in a cycle

        else: # Duplicate or out-of-order packet – do NOT reprocess
            print("Duplicate packet, seq =", seq)

            # Still acknowledge, so sender knows it was received
            msg = send_ack(seq)
        
        return msg


    def send_ack(self, ack_num, client_addr):
        # send cumulative ACK w/ flow control window
        
        # Args:
        # ack_num: sequence number
        # client_addr: address to send ACK to

        ack_packet = PRTPPacket(
            seq_num=self.seq_num,
            ack_num=ack_num,
            window_size=self.available_buffer,
            flags=PRTPPacket.FLAG_ACK
        )
        self.socket.sendto(ack_packet.serialize(), client_addr) # serialize contains checksum & checksum validation
        print(f"[RECEIVER] Sent cumulative ACK {ack_num} "f"(window={self.available_buffer}B, buffer_used={len(self.received_data)}B)")
        
    # Define Server Port
    serverPort = 12000

    # Create UDP Socket
    serverSocket = socket(AF_INET, SOCK_DGRAM)

    # Bind the socket to local port 12000
    serverSocket.bind(('', serverPort))


    print ("The server is ready to receive")
    def main():
        # MAIN SERVER LOOP
        while True: # Forever Loop
            # Read from UDP Socket into message & client address
            message, clientAddress = serverSocket.recvfrom(2048)

            sentence = message.decode()
            print("sentence: ",sentence)

            lines = sentence.split("\r\n")
            print("lines size: ",len(lines))
            try: #load sequence number
                if (len(lines) > 1):
                    sequence_number = lines[0]
                    ack = lines[2]
            except:
                print("Please input a number for sequence number")

            try: #load data
                if (len(lines) > 2):
                    for i in lines:
                        if(i > 4):
                            data += lines[i]
                            print("data: ",data)
            except:
                print("Please input a number for equence number")
            


            #print("data: ",data)
            modifiedMessage = handle_incoming_frame(sequence_number, data, send_ack)






            
            # Uppder Case (as the simple function intended)
            #modifiedMessage = message.decode().upper()
            
            # Send the upper case string back to the same client
            serverSocket.sendto(modifiedMessage.encode(), clientAddress)



    #TODO: implement flow & congestion control as part of a PRTP protocol, may have to create a new file to contain the packet data implementation

