import socket, time, btcp.packet, threading
from btcp.lossy_layer import LossyLayer
from btcp.btcp_socket import BTCPSocket
from btcp.constants import *
from random import randint
from btcp.util import State
from btcp.packet import TCPpacket


# The bTCP server socket
# A server application makes use of the services provided by bTCP by calling accept, recv, and close
class BTCPServerSocket(BTCPSocket):
    def __init__(self, window, timeout):
        super().__init__(window, timeout)
        self.window = window
        self.timeout = timeout
        self._lossy_layer = LossyLayer(self, SERVER_IP, SERVER_PORT, CLIENT_IP, CLIENT_PORT)
        self.state = State.LISTEN

    # Called by the lossy layer from another thread whenever a segment arrives
    def lossy_layer_input(self, segment):
        segment = btcp.packet.unpack_from_socket(segment)
        
        if not segment.confirm_checksum():
            # discard segment
            pass
        if segment.packet_type() == "SYN":
            self.state = State.SYN_RECVD
            response_thread = threading.Thread(target=self.handshake_response_thread, args=(segment,))
            response_thread.start()
        elif segment.packet_type() == "ACK":
            self.state = State.HNDSH_COMP
        elif segment.packet_type() == "FIN":
            self.state = State.FIN_RECVD
            con_close_thread = threading.Thread(target=self.connection_close_thread)
            con_close_thread.start()
            self.close()
        else: 
            pass

    # Wait for the client to initiate a three-way handshake
    def accept(self):
        pass

    # Send any incoming data to the application layer
    def recv(self):
        pass

    # Clean up any state
    def close(self):
        self._lossy_layer.destroy()
    
    # 
    def handshake_response_thread(self, segment):
        seq_nr = randint(0,65535) - segment.get_seq_nr()
        ack_nr = segment.get_seq_nr() + 1
        segment.up_seq_nr(seq_nr)
        segment.up_ack_nr(ack_nr)
        segment.set_flags(True, True, False)
        self._lossy_layer.send_segment(segment.pack())
        self.state = State.SYN_SEND
        while True: # as long as no ACK handshake segment is received
            time.sleep(self.timeout/1000)
            if (self.state != State.HNDSH_COMP):
                self._lossy_layer.send_segment(segment.pack())
            else:
                break
    
    # 
    def connection_close_thread(self):
        segment = TCPpacket()
        segment.set_flags(True, False, True)
        send_segment = segment.pack()
        self._lossy_layer.send_segment(send_segment)