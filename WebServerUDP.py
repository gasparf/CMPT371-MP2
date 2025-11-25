# Include Python's Socket Library
from socket import *
import time


#initialize checksum and sequence number

EXPECTED_SEQ = 0


def handle_incoming_frame(frame, send_ack):
    global EXPECTED_SEQ

    seq = frame["sequence_number"] #seq is the number assigned by the client to this packet
    data = frame["data"] #data is the payload

    if seq == EXPECTED_SEQ: #correct sequence number, process packet
        print("Received new packet:", data) #frame is the raw incoming "packet" you received, already decoded to Python dict of "{"seq": 3, "data": "hello"}""

        # Process packet normally
        process(data)

        # Send ACK
        send_ack(seq)

        EXPECTED_SEQ += 1      # Next expected packet, not in a cycle

    else:
        # Duplicate or out-of-order packet – do NOT reprocess
        print("Duplicate packet, seq =", seq)

        # Still acknowledge, so sender knows it was received
        send_ack(seq)


def send_ack(seq):
    ack_frame = { "ack": seq }
    raw_send(ack_frame)   # your low-level send


def process(data):
    print("Processing:", data)


# Define Server Port
serverPort = 12000

# Create UDP Socket
serverSocket = socket(AF_INET, SOCK_DGRAM)

# Bind the socket to local port 12000
serverSocket.bind(('', serverPort))


print ("The server is ready to receive")
while True: # Forever Loop
    # Read from UDP Socket into message & client address
    message, clientAddress = serverSocket.recvfrom(2048)



    handle_incoming_frame(message, send_ack)






    
    # Uppder Case (as the simple function intended)
    modifiedMessage = message.decode().upper()
    
    # Send the upper case string back to the same client
    serverSocket.sendto(modifiedMessage.encode(), clientAddress)
    print(modifiedMessage)


#TODO: implement flow & congestion control as part of a PRTP protocol, may have to create a new file to contain the packet data implementation

