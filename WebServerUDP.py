# Include Python's Socket Library
from socket import *
from prtp_packet import PRTPPacket
import sys
import time

class GoBackNReceiver:
    """
    Go-Back-N Receiver with 3-way handshake and Flow Control
    - Connection establishment (SYN -> SYN-ACK -> ACK)
    - Receives packets in order
    - Sends cumulative ACKs with advertised window
    - Discards out-of-order packets (Go-Back-N behavior)
    - Checksum validation for all packets
    """
    
    def __init__(self, port):
        """
        Initialize Go-Back-N Receiver
        
        Args:
            port: Local port to bind
        """
        self.socket = socket(AF_INET, SOCK_DGRAM)
        self.socket.bind(('', port))
        self.socket.settimeout(30.0)  # 30 second timeout for connection
        
        # Connection state
        self.connected = False
        self.client_addr = None
        self.seq_num = 0
        self.expected_seq = 0  # EXPECTED_SEQ from original code
        
        # Flow control
        self.MAX_BUFFER_SIZE = 65535
        self.received_data = b''
        self.available_buffer = self.MAX_BUFFER_SIZE
        
        print(f"[GBN RECEIVER] Listening on port {port}")
    
    def listen(self):
        """
        Wait for incoming connection and perform 3-way handshake
        Replaces the original connection setup
        
        Returns:
            bool: True if connection established
        """
        print(f"[HANDSHAKE] Waiting for connection...")
        
        try:
            # Step 1: Wait for SYN
            while True:
                data, addr = self.socket.recvfrom(PRTPPacket.MAX_PACKET_SIZE)
                syn_packet = PRTPPacket.deserialize(data)  # Validates checksum
                
                if syn_packet and syn_packet.has_flag(PRTPPacket.FLAG_SYN):
                    print(f"[HANDSHAKE] Received SYN from {addr} (seq={syn_packet.seq_num})")
                    self.client_addr = addr
                    
                    # Step 2: Send SYN-ACK
                    self.seq_num = 0
                    syn_ack_packet = PRTPPacket(
                        seq_num=self.seq_num,
                        ack_num=syn_packet.seq_num + 1,
                        window_size=self.available_buffer,
                        flags=PRTPPacket.FLAG_SYN | PRTPPacket.FLAG_ACK
                    )
                    self.socket.sendto(syn_ack_packet.serialize(), self.client_addr)  # Includes checksum
                    print(f"[HANDSHAKE] Sent SYN-ACK (seq={self.seq_num}, ack={syn_ack_packet.ack_num}, window={self.available_buffer}B)")
                    
                    # Step 3: Wait for ACK
                    data, addr = self.socket.recvfrom(PRTPPacket.MAX_PACKET_SIZE)
                    ack_packet = PRTPPacket.deserialize(data)  # Validates checksum
                    
                    if ack_packet and ack_packet.has_flag(PRTPPacket.FLAG_ACK):
                        print(f"[HANDSHAKE] Received ACK (seq={ack_packet.seq_num}, ack={ack_packet.ack_num})")
                        
                        # Connection established!
                        self.expected_seq = ack_packet.seq_num  # Initialize EXPECTED_SEQ
                        self.connected = True
                        
                        print(f"[HANDSHAKE] ✓ Connection established!")
                        print(f"[GBN RECEIVER] Flow control window: {self.available_buffer}B")
                        return True
                    else:
                        print("[HANDSHAKE] Invalid ACK, waiting for new SYN...")
                        continue
                        
        except timeout:
            print("[HANDSHAKE] Connection timeout")
            return False
        except Exception as e:
            print(f"[HANDSHAKE] Error: {e}")
            return False
    
    def handle_incoming_frame(self, packet):
        """
        Handle incoming data frame (replaces original handle_incoming_frame)
        Implements Go-Back-N receiver logic
        
        Args:
            packet: PRTPPacket object (already deserialized and checksum validated)
            
        Returns:
            bool: True if packet was accepted
        """
        seq_num = packet.seq_num
        
        if seq_num == self.expected_seq:
            # Correct sequence number - process packet
            print(f"[RECEIVER] ✓ Received new packet (seq={seq_num}, {len(packet.data)} bytes)")
            
            # Add to received data buffer
            self.received_data += packet.data
            
            # Update flow control window
            self.available_buffer = max(0, self.MAX_BUFFER_SIZE - len(self.received_data))
            
            # Send cumulative ACK
            self._send_ack(self.expected_seq, self.client_addr)
            
            # Move to next expected sequence
            self.expected_seq += 1
            
            return True
            
        elif seq_num < self.expected_seq:
            # Duplicate packet (already received)
            print(f"[RECEIVER] Duplicate packet (seq={seq_num}, expected={self.expected_seq})")
            
            # Re-send ACK for duplicate (helps sender recover faster)
            self._send_ack(seq_num, self.client_addr)
            
            return False
            
        else:
            # Out-of-order packet (seq_num > expected_seq)
            # Go-Back-N: DISCARD out-of-order packets
            print(f"[RECEIVER] ✗ Out-of-order packet (seq={seq_num}, expected={self.expected_seq}) - DISCARDING")
            
            # Send ACK for last correctly received packet (cumulative)
            if self.expected_seq > 0:
                self._send_ack(self.expected_seq - 1, self.client_addr)
            
            return False
    
    def _send_ack(self, ack_num, client_addr):
        """
        Send cumulative ACK with flow control window
        Replaces original send_ack() function
        
        Args:
            ack_num: Sequence number to acknowledge
            client_addr: Client address to send ACK to
        """
        ack_packet = PRTPPacket(
            seq_num=self.seq_num,
            ack_num=ack_num,
            window_size=self.available_buffer,  # Flow control
            flags=PRTPPacket.FLAG_ACK
        )
        self.socket.sendto(ack_packet.serialize(), client_addr)  # Includes checksum
        print(f"[RECEIVER] Sent cumulative ACK {ack_num} "
              f"(window={self.available_buffer}B, buffer_used={len(self.received_data)}B)")
    
    def receive(self, timeout_duration=10.0):
        """
        Receive data using Go-Back-N protocol with checksum validation
        
        Args:
            timeout_duration: Maximum time to wait for data
            
        Returns:
            bytes: Received data
        """
        if not self.connected:
            raise Exception("Not connected - call listen() first")
        
        self.socket.settimeout(1.0)
        
        print(f"[GBN RECEIVER] Waiting for packets (expected_seq={self.expected_seq})...")
        
        last_activity = time.time()
        idle_timeout = 30.0  # Stop receiving if no packets for 30 seconds (allows time for user input)
        
        while True:
            try:
                # Receive packet
                data, addr = self.socket.recvfrom(PRTPPacket.MAX_PACKET_SIZE)
                packet = PRTPPacket.deserialize(data)  # Validates checksum automatically
                
                if packet is None:
                    # Checksum validation failed
                    print("[SERVER RECEIVER] ✗ Invalid packet (checksum failed) - DISCARDING")
                    continue
                
                last_activity = time.time()
                
                # Handle the incoming frame using Go-Back-N logic
                self.handle_incoming_frame(packet)
            
            except timeout as e:
                # Check if we've been idle too long
                if time.time() - last_activity > idle_timeout:
                    if len(self.received_data) > 0:
                        print("[SERVER RECEIVER] No more packets, transfer complete")
                        break
                    else:
                        print("[SERVER RECEIVER] Timeout waiting for data")
                        return None
                continue
            except Exception as e:
                print(f"[GBN RECEIVER] Error: {e}")
                break
        
        return self.received_data
    
    def close(self):
        """Close socket"""
        self.socket.close()
        print("[SERVER RECEIVER] Socket closed")


def main():
    """Main server function"""
    # Define Server Port (from original code)
    serverPort = int(sys.argv[1]) if len(sys.argv) > 1 else 12000
    
    print("=" * 70)
    print("Go-Back-N PRTP Server")
    print("Connection-Oriented | Pipelined | Flow Control | Checksum Validation")
    print("=" * 70)
    print(f"Port: {serverPort}")
    print("-" * 70)
    
    # Create receiver ONCE outside the loop
    receiver = GoBackNReceiver(serverPort)
    
    while True:  # Forever Loop (from original code)
        try:
            # Wait for connection (3-way handshake)
            print("\n[SERVER] Waiting for new client connection...")
            if not receiver.listen():
                print("[SERVER] Connection failed, waiting for next client...")
                # Reset receiver state for next connection
                receiver.connected = False
                receiver.expected_seq = 0
                receiver.received_data = b''
                receiver.available_buffer = receiver.MAX_BUFFER_SIZE
                continue
            
            # Receive data using Go-Back-N with checksum validation
            received_data = receiver.receive()
            
            if received_data:
                # Process the data (Upper Case - as the simple function intended)
                original = received_data.decode('utf-8', errors='ignore')
                modifiedMessage = original.upper()  # From original code
                
                print("-" * 70)
                print(f"[SERVER] Received: '{original}'")
                print(f"[SERVER] Uppercase: '{modifiedMessage}'")
                print(f"[SERVER] Total bytes received: {len(received_data)}")
                print("-" * 70)
            
            # Reset receiver state for next connection (don't close socket!)
            receiver.connected = False
            receiver.expected_seq = 0
            receiver.received_data = b''
            receiver.available_buffer = receiver.MAX_BUFFER_SIZE
            print("\n[SERVER] Ready for next connection...")
            print("=" * 70)
        
        except KeyboardInterrupt:
            print("\n[SERVER] Shutting down...")
            receiver.close()
            break
        except Exception as e:
            print(f"[SERVER] Error: {e}")
            import traceback
            traceback.print_exc()
            # Reset state and continue
            receiver.connected = False
            receiver.expected_seq = 0
            receiver.received_data = b''
            receiver.available_buffer = receiver.MAX_BUFFER_SIZE


if __name__ == "__main__":
    main()