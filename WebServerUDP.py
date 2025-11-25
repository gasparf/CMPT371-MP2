# Include Python's Socket Library
from socket import *
import time


#initialize checksum and sequence number

EXPECTED_SEQ = 1
ack = "NAK"
data = ""
sequence_number = -1


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


def send_ack(seq):
    ack_message = str(seq)
    ack_message += "ACK"
    return ack_message   # your low-level send




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

    sentence = message.decode()
    print(sentence)

    lines = sentence.split("\r\n")
    try: #load sequence number
        if (len(lines) > 1):
            sequence_number = lines[0]
            ack = lines[2]
    except:
        print("Please input a number for sequence number")

    try: #load data
        if (len(lines) > 2):
            for i in lines:
                if(i > 1):
                    data += lines[i]
    except:
        print("Please input a number for equence number")
    


    print(sequence_number, data)
    modifiedMessage = handle_incoming_frame(sequence_number, data, send_ack)






    
    # Uppder Case (as the simple function intended)
    modifiedMessage = message.decode().upper()
    
    # Send the upper case string back to the same client
    serverSocket.sendto(modifiedMessage.encode(), clientAddress)
    print(modifiedMessage)


#TODO: implement flow & congestion control as part of a PRTP protocol, may have to create a new file to contain the packet data implementation

