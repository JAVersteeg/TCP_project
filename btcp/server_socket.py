import socket, time, btcp.packet, threading
from btcp.lossy_layer import LossyLayer
from btcp.btcp_socket import BTCPSocket
from btcp.constants import *
from random import randint
from btcp.packet import TCPpacket
from concurrent.futures import ThreadPoolExecutor
from btcp.state import State

# The bTCP server socket
# A server application makes use of the services provided by bTCP by calling accept, recv, and close
class BTCPServerSocket(BTCPSocket):
    def __init__(self, window, timeout):
        super().__init__(window, timeout)
        self.window = window
        self.timeout = timeout
        self.thread_executor = ThreadPoolExecutor(max_workers=window)
        self._lossy_layer = LossyLayer(self, SERVER_IP, SERVER_PORT, CLIENT_IP, CLIENT_PORT)
        self.state = State.CLOSED

    # Called by the lossy layer from another thread whenever a segment arrives
    def lossy_layer_input(self, segment):
        segment = btcp.packet.unpack_from_socket(segment)
        
        if not segment.confirm_checksum() or self.state == State.CLOSED:
            # discard segment
            pass
        if segment.packet_type() == "SYN":
            self.state = State.SYN_RECVD
            self.thread_executor.submit(self.handshake_response_thread, segment)
        elif segment.packet_type() == "ACK":
            self.state = State.HNDSH_COMP
        elif segment.packet_type() == "FIN":
            self.state = State.FIN_RECVD
            self.close_connection()
            self.close()
        else: 
            pass

    # Wait for the client to initiate a three-way handshake
    def accept(self):
        self.state = State.LISTEN

    # Send any incoming data to the application layer
    def recv(self):
        pass

    # Clean up any state
    def close(self):
        self.thread_executor.shutdown(wait=True)
        print("DESTROY SERVER SOCKET")
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
    def close_connection(self):
        segment = TCPpacket()
        segment.set_flags(True, False, True)
        send_segment = segment.pack()
        self._lossy_layer.send_segment(send_segment)