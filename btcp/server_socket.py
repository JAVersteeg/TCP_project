import socket, time, btcp.packet, threading
from btcp.lossy_layer import LossyLayer
from btcp.btcp_socket import BTCPSocket
from btcp.constants import *
from random import randint
from btcp.state import State
from btcp.packet import TCPpacket
from concurrent.futures import ThreadPoolExecutor

# The bTCP server socket
# A server application makes use of the services provided by bTCP by calling accept, recv, and close
class BTCPServerSocket(BTCPSocket):
    def __init__(self, window, timeout):
        super().__init__(window, timeout)
        self.window = window
        self.timeout = timeout
        self.thread_executor = ThreadPoolExecutor(max_workers=window)
        self._lossy_layer = LossyLayer(self, SERVER_IP, SERVER_PORT, CLIENT_IP, CLIENT_PORT)
        self.segment_buffer = {}    # segments that are received out of order
        self.data_collection = []       # data section of segments that are received in order, gets turned into output file
        self.exp_seq_nr = 0        # sequence number of packet that is expected next
        self.state = State.CLOSED
        # start thread that checks segment_buffer when exp_seq_nr is updated.

    # Called by the lossy layer from another thread whenever a segment arrives
    def lossy_layer_input(self, packet):
        segment = btcp.packet.unpack_from_socket(packet)
        if not segment.confirm_checksum() or self.state == State.CLOSED:
            # discard segment
            pass
        if segment.packet_type() == "SYN":
            self.state = State.SYN_RECVD
            self.thread_executor.submit(self.handshake_response_thread, segment)
        elif segment.packet_type() == "ACK":
            self.state = State.HNDSH_COMP
            # exp_seq_nr = sequence number advertised by client in this segment.
        elif segment.packet_type() == "FIN":
            self.state = State.FIN_RECVD
        elif segment.pack_type() == "DATA":     
            self.send_data_ack(segment)
            if segment.getattr(segment, 'seq_nr') == self.exp_seq_nr:
                data = getattr(segment, 'data')
                self.data_collection.append(data)
                self.exp_seq_nr += 1
            else:
                seq_nr = getattr(segment, 'seq_nr')
                entry = {str(seq_nr) : segment}
                self.segment_buffer.update(entry)
        else:
            print("Unknown packet type: ", segment.packet_type())

    # Wait for the client to initiate a three-way handshake
    def accept(self):
        self.state = State.LISTEN
        '''start update_buffer_thread()'''

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
        segment.set_flags(ACK=True, SYN=True)
        self._lossy_layer.send_segment(segment.pack())
        self.state = State.SYN_SEND
        while True: # as long as no ACK handshake segment is received
            time.sleep(self.timeout/1000)
            if (self.state != State.HNDSH_COMP):
                self._lossy_layer.send_segment(segment.pack())
            else:
                break
    
    #
    def send_data_ack(self, segment):
        segment.remove_data()
        segment.up_ack_nr(getattr(segment, 'seq_nr'))
        segment.reset_seq_nr()
        segment.set_flags(ACK=True)
        self._lossy_layer.send_segment(segment)
    
    #    
    def update_buffer_thread(self):
        while self.state != State.CLOSED:
            seq_nr = self.exp_seq_nr
            seq_nr_key = str(seq_nr)
            try:                
                segment = self.segment_buffer[seq_nr_key]
                data = getattr(segment, 'data')
                self.data_collection.append(data)
                del self.segment_buffer[seq_nr_key]
                self.exp_seq_nr += 1
            except KeyError as error:
                print(error)