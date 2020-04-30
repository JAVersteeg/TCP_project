import socket
from btcp.lossy_layer import LossyLayer
from btcp.btcp_socket import BTCPSocket
from btcp.constants import *
import btcp.packet
from random import randint
from btcp.util import State


# The bTCP server socket
# A server application makes use of the services provided by bTCP by calling accept, recv, and close
class BTCPServerSocket(BTCPSocket):
    def __init__(self, window, timeout):
        super().__init__(window, timeout)
        self._lossy_layer = LossyLayer(self, SERVER_IP, SERVER_PORT, CLIENT_IP, CLIENT_PORT)
        self.state = State.LISTEN

    # Called by the lossy layer from another thread whenever a segment arrives
    def lossy_layer_input(self, segment):
        segment = btcp.packet.unpack_from_socket(segment)
        if not segment.confirm_checksum():
            # discard segment
            pass
        if segment.packet_type() == "SYN":
            print("SERVER RECEIVED: ", segment)
            syn_response = self.create_handshake_response(segment)
            self._lossy_layer.send_segment(syn_response.pack())

    # Wait for the client to initiate a three-way handshake
    def accept(self):
        pass

    # Send any incoming data to the application layer
    def recv(self):
        pass

    # Clean up any state
    def close(self):
        self._lossy_layer.destroy()
        
    def create_handshake_response(self, segment):
        seq_nr = randint(0,65535) - segment.get_seq_nr()
        segment.up_seq_nr(seq_nr)
        ack_nr = segment.get_seq_nr() + 1
        segment.up_ack_nr(ack_nr)
        segment.set_flags(True, True, False)    
        return segment
