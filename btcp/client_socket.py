from btcp.btcp_socket import BTCPSocket
from btcp.lossy_layer import LossyLayer
from btcp.constants import *
from btcp.packet import TCPpacket
import btcp.packet, time, threading
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
        segment = btcp.packet.unpack_from_socket(segment)
        segment_type = segment.packet_type()
        if (segment_type == "SYN-ACK"):
            self.state = State.SYN_ACK_RECVD
            ack_thread = threading.Thread(target=self.handshake_ack_thread, args=(segment,))
            ack_thread.start()
        else:
            pass

    # Initiate a three-way handshake with the server.
    def connect(self):
        connect_thread = threading.Thread(target=self.con_establish_thread)
        connect_thread.start()
        self.state = State.SYN_SEND
        
    # Send the response to the server's ACK of the handshake.
    def handshake_ack_thread(self, segment):
        seq_nr = segment.get_ack_nr() + 1
        ack_nr = segment.get_seq_nr() + 1
        segment.up_seq_nr(seq_nr - (ack_nr -1)) # remove old seq_nr (which is now ack_nr) and replace by new seq_nr
        segment.up_ack_nr(ack_nr - seq_nr) # remove als ack_nr (which is now seq_nr) and replace by new ack_nr
        segment.set_flags(True, False, False) # set ACK flag
        self._lossy_layer.send_segment(segment.pack())
        
    
    # Send data originating from the application in a reliable way to the server
    def send(self, data):
        pass

    # Perform a handshake to terminate a connection
    def disconnect(self):
        pass

    # Clean up any state
    def close(self):
        self._lossy_layer.destroy()
        
    def con_establish_thread(self):
        syn_nr = randint(0,65535) # random 16-bit integer
        segment = TCPpacket(syn_nr)
        segment.set_flags(False, True, False) # set SYN flag
        self._lossy_layer.send_segment(segment.pack())
        while True:
            
            time.sleep(self.timeout/1000)
            if self.state != State.SYN_ACK_RECVD:
                self._lossy_layer.send_segment(segment.pack())
            else:
                self.state = State.HNDSH_COMP
                break
        
