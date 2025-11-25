# Include Python's Socket Library
from socket import *
from prtp_packet import PRTPPacket
import threading
import time
import sys

class GoBackNSender:
    # Go-Back-N Sender Implementation with Flow & Congestion Control
    # - Sliding window protocol
    # - Cumulative ACKs
    # - Retransmit all unacknowledged packets on timeout
    # - AIMD congestion control (Additive Increase, Multiplicative Decrease)
    # - Flow control via receiver advertised window
    
    def __init__(self, window_size=5, timeout=2.0):
        """
        Initialize Go-Back-N Sender
        
        Args:
            window_size: Initial maximum number of unacknowledged packets
            timeout: Timeout interval in seconds
        """
        self.socket = socket(AF_INET, SOCK_DGRAM)
        self.socket.settimeout(0.1)  # Non-blocking for ACK reception
        
        # Go-Back-N parameters
        self.max_window_size = window_size  # Maximum allowed window
        self.timeout = timeout
        self.MSS = PRTPPacket.MAX_DATA_SIZE  # Maximum Segment Size
        
        # Sequence numbers
        self.base = 0  # Oldest unacknowledged packet
        self.next_seq_num = 0  # Next packet to send
        
        # Packet storage for retransmission
        self.send_buffer = {}  # {seq_num: (packet, timestamp)}
        
        # Connection state
        self.connected = False
        self.peer_addr = None
        
        # ---- CONGESTION CONTROL (AIMD) ----
        self.cwnd = 1.0  # Congestion window (in packets)
        self.ssthresh = 16.0  # Slow start threshold (in packets)
        self.state = 'slow_start'  # States: 'slow_start', 'congestion_avoidance'
        
        # ---- FLOW CONTROL ----
        self.receiver_window = 65535  # Receiver advertised window (in bytes)
        
        # Threading
        self.running = False
        self.ack_thread = None
        self.timer_thread = None
        self.lock = threading.Lock()
        
        # Timer
        self.timer_running = False
        self.timer_start = None
    
    # ---- CONNECTION-ORIENTED ----
    def connect(self, host, port):
        """Establish connection using 3-way handshake (SYN -> SYN-ACK -> ACK)"""
        self.peer_addr = (host, port)
        
        # Enable blocking mode for handshake
        self.socket.settimeout(5.0)
        
        try:
            # Step 1: Send SYN
            print(f"[HANDSHAKE] Initiating connection to {host}:{port}")
            syn_packet = PRTPPacket(
                seq_num=0,
                ack_num=0,
                flags=PRTPPacket.FLAG_SYN
            )
            self.socket.sendto(syn_packet.serialize(), self.peer_addr)
            print(f"[HANDSHAKE] Sent SYN (seq=0)")
            
            # Step 2: Receive SYN-ACK
            data, addr = self.socket.recvfrom(PRTPPacket.MAX_PACKET_SIZE)
            syn_ack_packet = PRTPPacket.deserialize(data)
            
            if not syn_ack_packet or \
               not syn_ack_packet.has_flag(PRTPPacket.FLAG_SYN) or \
               not syn_ack_packet.has_flag(PRTPPacket.FLAG_ACK):
                print("[HANDSHAKE] Failed: Invalid SYN-ACK")
                return False
            
            print(f"[HANDSHAKE] Received SYN-ACK (seq={syn_ack_packet.seq_num}, ack={syn_ack_packet.ack_num})")
            
            # Extract receiver window from SYN-ACK
            self.receiver_window = syn_ack_packet.window_size if syn_ack_packet.window_size > 0 else 65535
            
            # Step 3: Send ACK
            ack_packet = PRTPPacket(
                seq_num=syn_ack_packet.ack_num,
                ack_num=syn_ack_packet.seq_num + 1,
                flags=PRTPPacket.FLAG_ACK,
                window_size=0  # Client doesn't receive data in this implementation
            )
            self.socket.sendto(ack_packet.serialize(), self.peer_addr)
            print(f"[HANDSHAKE] Sent ACK (seq={ack_packet.seq_num}, ack={ack_packet.ack_num})")
            
            # Connection established!
            self.connected = True
            self.base = ack_packet.seq_num
            self.next_seq_num = ack_packet.seq_num
            
            # Return to non-blocking mode for data transfer
            self.socket.settimeout(0.1)
            
            # Start ACK receiver thread
            self.running = True
            self.ack_thread = threading.Thread(target=self._receive_acks, daemon=True)
            self.ack_thread.start()
            
            print(f"[HANDSHAKE] ✓ Connection established!")
            print(f"[CLIENT SENDER] Initial cwnd: {self.cwnd} packets, Slow Start Threshold: {self.ssthresh} packets")
            print(f"[CLIENT SENDER] Receiver window: {self.receiver_window} bytes")
            return True
            
        except timeout:
            print("[HANDSHAKE] Connection timeout")
            return False
        except Exception as e:
            print(f"[HANDSHAKE] Connection failed: {e}")
            return False
    
    
    def send_data(self, data):
        # Send data using Go-Back-N protocol
        
        # Args:
        #     data: bytes to send
        
        if not self.connected:
            raise Exception("Not connected")
        
        # Split data into chunks (max 1024 bytes per packet)
        max_chunk_size = PRTPPacket.MAX_DATA_SIZE
        chunks = [data[i:i+max_chunk_size] for i in range(0, len(data), max_chunk_size)]
        
        total_packets = len(chunks)
        print(f"[CLIENT SENDER] Sending {len(data)} bytes in {total_packets} packets")
        
        chunk_index = 0
        
        while self.base < total_packets:
            with self.lock:
                # Calculate effective window (min of congestion window and flow control window)
                # Convert receiver window from bytes to packets
                receiver_window_packets = self.receiver_window / self.MSS
                effective_window = min(int(self.cwnd), int(receiver_window_packets), self.max_window_size)
                
                # Send packets within effective window
                while self.next_seq_num < total_packets and \
                      self.next_seq_num < self.base + effective_window:
                    
                    # Create packet
                    packet = PRTPPacket(
                        seq_num=self.next_seq_num,
                        ack_num=0,
                        flags=PRTPPacket.FLAG_ACK,
                        data=chunks[self.next_seq_num]
                    )
                    
                    # Send packet
                    self.socket.sendto(packet.serialize(), self.peer_addr)
                    
                    # Calculate bytes in flight
                    bytes_in_flight = (self.next_seq_num - self.base + 1) * self.MSS
                    
                    print(f"[CLIENT SENDER] Sent packet {self.next_seq_num} "
                          f"(cwnd={self.cwnd:.2f}, rwnd={receiver_window_packets:.1f}, "
                          f"effective={effective_window}")
                    
                    # Store for potential retransmission
                    self.send_buffer[self.next_seq_num] = (packet, time.time())
                    
                    # Start timer if this is the first packet in window
                    if self.base == self.next_seq_num:
                        self._start_timer()
                    
                    self.next_seq_num += 1
            
            # Wait a bit for ACKs
            time.sleep(0.01)
            
            # Check for timeout
            with self.lock:
                if self.timer_running and self.base < total_packets:
                    elapsed = time.time() - self.timer_start
                    if elapsed >= self.timeout:
                        # Congestion detected, initiate retransmission
                        print(f"[CLIENT SENDER] TIMEOUT! Retransmitting packets from {self.base}")
                        
                        # ---- CONGESTION CONTROL: Multiplicative Decrease (MD) ----
                        # AIMD: On timeout, halve cwnd and reset to slow start
                        self.ssthresh = max(self.cwnd / 2, 2.0)
                        self.cwnd = 1.0  # Reset to 1 packet
                        self.state = 'slow_start'
                        print(f"[CONGESTION] TIMEOUT! Multiplicative Decrease: "
                              f"cwnd={self.cwnd:.2f}, ssthresh={self.ssthresh:.2f}")
                        
                        # Retransmit all packets in window (Go-Back-N)
                        self._retransmit_window()
                        self._start_timer()
        
        print(f"[CLIENT SENDER] All {total_packets} packets acknowledged!")
        return len(data)
    
    def _receive_acks(self):
        # Background thread to receive ACKs
        while self.running:
            try:
                data, addr = self.socket.recvfrom(PRTPPacket.MAX_PACKET_SIZE)
                ack_packet = PRTPPacket.deserialize(data)
                
                if ack_packet and ack_packet.has_flag(PRTPPacket.FLAG_ACK):
                    self._handle_ack(ack_packet)
            except timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"[CLIENT SENDER] Error receiving ACK: {e}")
    
    def _handle_ack(self, ack_packet):
        # Handle received ACK (cumulative) with AIMD congestion control
        # In Go-Back-N, ACK n means all packets up to and including n are received

        with self.lock:
            ack_num = ack_packet.ack_num
            
            # ---- FLOW CONTROL: Extract receiver window from ACK ----
            self.receiver_window = ack_packet.window_size if ack_packet.window_size > 0 else 65535
            
            if ack_num >= self.base:
                # Count how many NEW packets are acknowledged
                newly_acked = ack_num - self.base + 1
                
                print(f"[CLIENT SENDER] Received ACK {ack_num} (cumulative, +{newly_acked} new, rwnd={self.receiver_window}B)")
                
                # Remove acknowledged packets from buffer
                for seq in range(self.base, ack_num + 1):
                    if seq in self.send_buffer:
                        del self.send_buffer[seq]
                
                # ---- CONGESTION CONTROL: Update cwnd using AIMD ----
                if self.state == 'slow_start':
                    # Slow Start: Increase cwnd by 1 for each ACK (exponential growth)
                    self.cwnd += newly_acked
                    
                    if self.cwnd >= self.ssthresh:
                        self.state = 'congestion_avoidance'
                        print(f"[CONGESTION] Entering congestion avoidance (cwnd={self.cwnd:.2f}, ssthresh={self.ssthresh:.2f})")
                    else:
                        print(f"[CONGESTION] Slow start: cwnd={self.cwnd:.2f} (ssthresh={self.ssthresh:.2f})")
                
                elif self.state == 'congestion_avoidance':
                    # Congestion Avoidance: Additive Increase (AI)
                    # Increase cwnd by 1/cwnd for each ACK (linear growth)
                    self.cwnd += (newly_acked / self.cwnd)
                    print(f"[CONGESTION] Congestion avoidance: cwnd={self.cwnd:.2f} (AI)")
                
                # Slide window forward
                self.base = ack_num + 1
                
                # Restart timer if there are still unacknowledged packets
                if self.base < self.next_seq_num:
                    self._start_timer()
                else:
                    self._stop_timer()
    
    def _retransmit_window(self):
        # Retransmit all packets in current window (Go-Back-N behavior)
        for seq_num in range(self.base, self.next_seq_num):
            if seq_num in self.send_buffer:
                packet, _ = self.send_buffer[seq_num]
                self.socket.sendto(packet.serialize(), self.peer_addr)
                self.send_buffer[seq_num] = (packet, time.time())
                print(f"[CLIENT SENDER] Retransmitted packet {seq_num}")
    
    def _start_timer(self):
        # Start/restart the timeout timer
        self.timer_running = True
        self.timer_start = time.time()
    
    def _stop_timer(self):
        # Stop the timeout timer
        self.timer_running = False
        self.timer_start = None
    
    def close(self):
        # Close connection
        self.running = False
        if self.ack_thread:
            self.ack_thread.join(timeout=1.0)
        self.socket.close()
        print("[GBN SENDER] Connection closed")


def main():
    # Main client function
    if len(sys.argv) < 3:
        print("Usage: python3 WebClientUDP.py <host> <port> [max_window_size]")
        sys.exit(1)
    
    serverName = sys.argv[1]
    serverPort = int(sys.argv[2])
    max_window_size = int(sys.argv[3]) if len(sys.argv) > 3 else 64  # Larger default for AIMD
    
    print("=" * 60)
    print("Go-Back-N Client with Flow & Congestion Control (AIMD)")
    print("=" * 60)
    
    try:
        # Create Go-Back-N sender with flow & congestion control
        sender = GoBackNSender(window_size=max_window_size, timeout=2.0)
        
        # Connect to server
        if sender.connect(serverName, serverPort):
            # Get message from user
            message = input('Input lowercase sentence: ')
            
            print(f"\n[CLIENT] Sending message: '{message}'")
            print(f"[CLIENT] Message size: {len(message)} bytes")
            print("-" * 60)
            
            # Send data using Go-Back-N with AIMD
            start_time = time.time()
            bytes_sent = sender.send_data(message.encode('utf-8'))
            end_time = time.time()
            
            print("-" * 60)
            print(f"[CLIENT] Successfully sent {bytes_sent} bytes")
            print(f"[CLIENT] Transfer time: {end_time - start_time:.3f} seconds")
            print(f"[CLIENT] Final cwnd: {sender.cwnd:.2f} packets")
            print(f"[CLIENT] Final state: {sender.state}")
            
            # Wait a bit for final ACKs
            time.sleep(0.5)
            
            # Close connection
            sender.close()
        else:
            print("[CLIENT] Failed to connect")
            sys.exit(1)
    
    except KeyboardInterrupt:
        print("\n[CLIENT] Interrupted by user")
    except Exception as e:
        print(f"[CLIENT] Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()


    
