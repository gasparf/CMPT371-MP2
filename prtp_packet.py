"""
Defines the packet structure for Pipelined Reliable Transfer Protocol
"""

import struct
import time

class PRTPPacket:
    # PRTP Packet Structure (20 bytes header + data):
    
    # Header Format (20 bytes):
    # - Sequence Number (4 bytes, unsigned int)
    # - Acknowledgment Number (4 bytes, unsigned int)
    # - Receiver Window Size (2 bytes, unsigned short)
    # - Checksum (2 bytes, unsigned short)
    # - Flags (1 byte): SYN, ACK, FIN, RST
    # - Reserved (3 bytes)
    # - Timestamp (4 bytes, unsigned int, milliseconds)
    
    # Flags:
    # - SYN (0x01): Synchronize, used in connection establishment
    # - ACK (0x02): Acknowledgment
    # - FIN (0x04): Finish, used in connection termination
    # - RST (0x08): Reset connection

    
    HEADER_SIZE = 20
    MAX_DATA_SIZE = 1024  # Maximum payload size
    MAX_PACKET_SIZE = HEADER_SIZE + MAX_DATA_SIZE
    
    # Flag constants
    FLAG_SYN = 0x01
    FLAG_ACK = 0x02
    FLAG_FIN = 0x04
    FLAG_RST = 0x08
    
    def __init__(self, seq_num=0, ack_num=0, window_size=0, flags=0, data=b''):
        # Initialize a PRTP packet
        
        # Args:
        #     seq_num: Sequence number
        #     ack_num: Acknowledgment number
        #     window_size: Receiver window size in bytes
        #     flags: Control flags (SYN, ACK, FIN, RST)
        #     data: Payload data (bytes)
        self.seq_num = seq_num
        self.ack_num = ack_num
        self.window_size = window_size
        self.flags = flags
        self.data = data
        self.timestamp = int(time.time() * 1000) % (2**32)  # milliseconds, mod 2^32
        self.checksum = 0
    
    def set_flag(self, flag):
        # Set a specific flag
        self.flags |= flag
    
    def has_flag(self, flag):
        # Check if a specific flag is set
        return (self.flags & flag) != 0
    
    def calculate_checksum(self):
        
        # Calculate checksum for the packet
        # Uses Internet checksum algorithm (16-bit one's complement)
        
        # Create header with checksum = 0
        header = struct.pack('!IIHHBBBBI',
                            self.seq_num,
                            self.ack_num,
                            self.window_size,
                            0,  # checksum placeholder
                            self.flags,
                            0,  # reserved byte 1
                            0,  # reserved byte 2
                            0,  # reserved byte 3
                            self.timestamp)
        
        # Combine header and data
        packet = header + self.data
        
        # Calculate checksum
        checksum = 0
        # Process 16-bit words
        for i in range(0, len(packet), 2):
            if i + 1 < len(packet):
                word = (packet[i] << 8) + packet[i + 1]
            else:
                word = packet[i] << 8
            checksum += word
            checksum = (checksum & 0xFFFF) + (checksum >> 16)
        
        # One's complement
        return ~checksum & 0xFFFF
    
    def serialize(self):
        # Serialize packet to bytes for transmission
        
        # Returns:
        #     bytes: Serialized packet

        # Calculate checksum
        self.checksum = self.calculate_checksum()
        
        # Pack header
        header = struct.pack('!IIHHBBBBI',
                            self.seq_num,
                            self.ack_num,
                            self.window_size,
                            self.checksum,
                            self.flags,
                            0,  # reserved byte 1
                            0,  # reserved byte 2
                            0,  # reserved byte 3
                            self.timestamp)
        
        return header + self.data
    
    @staticmethod
    def deserialize(packet_bytes):

        # Deserialize bytes to PRTP packet
        
        # Args:
        #     packet_bytes: Raw packet bytes
            
        # Returns:
        #     PRTPPacket: Deserialized packet or None if invalid

        if len(packet_bytes) < PRTPPacket.HEADER_SIZE:
            return None
        
        # Unpack header
        try:
            seq_num, ack_num, window_size, checksum, flags, _, _, _, timestamp = \
                struct.unpack('!IIHHBBBBI', packet_bytes[:PRTPPacket.HEADER_SIZE])
        except struct.error:
            return None
        
        # Extract data
        data = packet_bytes[PRTPPacket.HEADER_SIZE:]
        
        # Create packet
        packet = PRTPPacket(seq_num, ack_num, window_size, flags, data)
        packet.timestamp = timestamp
        
        # Verify checksum
        received_checksum = checksum
        packet.checksum = 0
        calculated_checksum = packet.calculate_checksum()
        
        if received_checksum != calculated_checksum:
            return None  # Checksum mismatch
        
        packet.checksum = received_checksum
        return packet
    
    def __str__(self):
        # String representation of packet
        flags_str = []
        if self.has_flag(self.FLAG_SYN):
            flags_str.append('SYN')
        if self.has_flag(self.FLAG_ACK):
            flags_str.append('ACK')
        if self.has_flag(self.FLAG_FIN):
            flags_str.append('FIN')
        if self.has_flag(self.FLAG_RST):
            flags_str.append('RST')
        
        return (f"PRTPPacket(seq={self.seq_num}, ack={self.ack_num}, "
                f"win={self.window_size}, flags={','.join(flags_str) or 'NONE'}, "
                f"data_len={len(self.data)})")
