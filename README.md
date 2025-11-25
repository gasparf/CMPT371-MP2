# CMPT371-MP2

Hello --YanTing

### CMPT371-MP2

Hello --YanTing

# Instruction to run program

1. ensure you are cd into CMPT371-MP2

2. Start the server " python3 WebServerUDP.py 12000 "

2a. " python3 WebServerUDP.py 12000 0.1 " for 10% packet loss

2b. " python3 WebClientUDP.py localhost 12000 64 0.15 " for 15% ACK loss on client

3. Start the client " python3 WebClientUDP.py localhost 12000 64 " --> local hose is the server hostname, 12000 is the port number, and 64 is the max window size (optional parameter)