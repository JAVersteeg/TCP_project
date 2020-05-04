from btcp.btcp_socket import BTCPSocket
from btcp.lossy_layer import LossyLayer
from btcp.constants import *
from btcp.packet import TCPpacket
import btcp.packet, time
from random import randint
from btcp.util import State

# bTCP client socket
# A client application makes use of the services provided by bTCP by calling connect, send, disconnect, and close
class BTCPClientSocket(BTCPSocket):
    def __init__(self, window, timeout):
        super().__init__(window, timeout)
        self.window = window
        self.timeout = timeout
        self._lossy_layer = LossyLayer(self, CLIENT_IP, CLIENT_PORT, SERVER_IP, SERVER_PORT)
        self.state = State.CLOSED
        
    # Called by the lossy layer from another thread whenever a segment arrives. 
    def lossy_layer_input(self, segment):
        packet = btcp.packet.unpack_from_socket(segment)
        packet_type = packet.packet_type()
        if (packet_type == "SYN-ACK"):
            self.state = State.SYN_RECVD
            print ("SYN-ACK RECVD")
            self.send_connect_ack(packet)
        else:
            pass

    # Initiate a three-way handshake with the server.
    def connect(self):
        self.state = State.SYN_SEND
        packet = self.create_init_segment()
        self._lossy_layer.send_segment(packet)
        self.state = State.TIME_WAIT # heeft een handshake geinitieerd en wacht op een respons of timeout.
        while True:
            time.sleep(self.timeout/1000)
            print("TIMEOUT")
            if (self.state != State.SYN_RECVD):
                self._lossy_layer.send_segment(packet)
            else:
                break
            
    # Send the response to the server's ACK of the handshake.
    def send_connect_ack(self, packet):
        seq_nr = packet.get_ack_nr() + 1
        ack_nr = packet.get_seq_nr() + 1
        packet.up_seq_nr(seq_nr - (ack_nr -1)) # remove old seq_nr (which is now ack_nr) and replace by new seq_nr
        packet.up_ack_nr(ack_nr - seq_nr) # remove als ack_nr (which is now seq_nr) and replace by new ack_nr
        packet.set_flags(True, False, False) # set ACK flag
        print("ACK: ", packet)
        packet = packet.pack()
        self._lossy_layer.send_segment(packet)
    
    # Send data originating from the application in a reliable way to the server
    def send(self, data):
        pass

    # Perform a handshake to terminate a connection
    def disconnect(self):
        pass

    # Clean up any state
    def close(self):
        self._lossy_layer.destroy()
        
    def create_init_segment(self):
        syn_nr = randint(0,65535) # random 16-bit integer
        packet = TCPpacket(syn_nr)
        packet.set_flags(False, True, False) # set SYN flag
        return packet.pack()
        
