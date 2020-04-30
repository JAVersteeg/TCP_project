from random import randint
from struct import pack, unpack
from enum import Enum
from binascii import crc32

DEBUG = True

header_format = "HHBBHI"

class TCPpacket:
    
    def __init__(self, syn_nr = 0, ack_nr = 0, 
                  flags = 0, window = 255, data_length = 1008, checksum = 0, 
                  data = b""):
        """Constructor of the packet"""
        self.syn_nr = syn_nr
        self.ack_nr = ack_nr
        self.flags = flags
        self.window = window 
        self.data_length = data_length  #defines how much of the 1008 bytes is data
        self.checksum = checksum 
        self.data = data
        if (checksum == 0): #if checksum is not defined (renew packet) calculate correct checksum
            self.checksum = self.calculate_checksum()
    
    def __str__(self):
        """Prints all attributes of the packet"""
        buf = ['SYN_Number: {}'.format(self.syn_nr)]
        buf.append('ACK_Number: {}'.format(self.ack_nr))
        buf.append('Flags: {}'.format(self.flags))
        buf.append('Window_size: {}'.format(self.window))
        buf.append('Data Length: {}'.format(self.data_length))
        buf.append('Checksum: {}'.format(self.checksum))
        buf.append('Data: {}'.format(self.data))
        return '\n'.join(buf)
        
        
    def pack(self):
        #print('Pack debug:\n', self)
        return pack(header_format, self.syn_nr, self.ack_nr,
                    self.flags, self.window, self.data_length, self.checksum) + self.data
    
    def calculate_checksum(self):
        "Calculates the checksum over the tcp packet variables."
        setattr(self, 'checksum', 0)
        return crc32(self.pack())
    
    def update_checksum(self):
        self.checksum = self.calculate_checksum()
     
    def set(self, attr, value):
        """Sets the choses attribute of the packet to the given value"""
        self.__dict__[attr] = value
        self.data_length = len(self.data)
        self.update_checksum()
    
    def remove_data(self):
        """Removes the data of a packet by replacing it with an empty bytestring"""
        self.data = b""
    
    def set_flags(self, ACK=False, SYN=False, FIN=False):
        """Sets the flags of a packet and then updates the checksum"""
        if ACK:
            self.flags = self.flags | 16
        elif (self.flags & 16) == 16: #if ack flag is set deactivate ack
            self.flags = self.flags ^ 16 
        if SYN:
            self.flags = self.flags | 2
        elif (self.flags & 2) == 2: #if syn flag is set deactivate syn
            self.flags = self.flags ^ 2
        if FIN:
            self.flags = self.flags | 1
        elif (self.flags & 1) == 1: #if fin flag is set deactivate fin
            self.flags = self.flags ^ 1
        self.update_checksum()
    
    def packet_type(self):
        """Returns the packet type as a string"""
        packet_type = ""
        if self.flags == 2:
            packet_type = "SYN"
        elif self.flags == 16:
            packet_type = "ACK"
        elif self.flags ==  1:
            packet_type = "FIN"
        elif self.flags == 18:
            packet_type = "SYN-ACK"
        elif self.flags == 17:
            packet_type = "FIN-ACK"
        elif self.data != b"":
            packet_type = "DATA"
        return packet_type
    
    def up_syn_nr(self, value):
        """
            Updates the syn number of a packet by adding 'value' to the current
            syn number of the packet and then updating the checksum of this 
            packet (because since the contents have changed)
        """
        self.syn_nr = self.syn_nr + value
        self.update_checksum()
        
    def up_ack_nr(self, value):
        """
            Updates the ack number of a packet by adding 'value' to the current
            ack number of the packet and then updating the checksum of this 
            packet (because the contents have changed)
        """
        self.ack_nr = self.ack_nr + value
        self.update_checksum()
    
    def confirm_checksum(self):
        own_checksum = self.checksum
        recalculated_check = self.calculate_checksum()
        return own_checksum == recalculated_check

    

def get_packet_from_stream(bytes):
    header_vars = unpack(header_format, bytes[0:16])
    data = bytes[16:]
    packet = TCPpacket(*header_vars, data)     #*var unpacks list to vars [a, b] -> a,b
    if DEBUG:
        print("Received:", packet.packet_type())
        print("{}\n".format(packet))
    return packet