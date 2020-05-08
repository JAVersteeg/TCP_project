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
        self.segment_buffer = {}    # segments that are received out-of-order
        self.data_collection = []   # data section of segments that are received in-order, eventually gets turned into output file
        self.hndsh_seq_nr = 0
        self.exp_seq_nr = 0         # sequence number of the next in-order packet.
        self.state = State.CLOSED
        self.thread_executor.submit(self.update_buffer_thread)  # start thread that checks segment_buffer for next in-order packet.

    # Called by the lossy layer from another thread whenever a segment arrives
    def lossy_layer_input(self, packet):
        segment = btcp.packet.unpack_from_socket(packet)
        if not segment.confirm_checksum() or self.state == State.CLOSED:
            # spoel segment door het toilet
            pass
        else:
            if segment.packet_type() == "SYN":
                self.state = State.SYN_RECVD
                self.thread_executor.submit(self.handshake_response_thread, segment)
            elif segment.packet_type() == "ACK" and segment.get_ack_nr() == self.hndsh_seq_nr + 1:
                print("Server received ACK")
                self.state = State.HNDSH_COMP
                self.exp_seq_nr = segment.get_seq_nr()
            elif segment.packet_type() == "FIN":
                self.state = State.FIN_RECVD
                print("Server received FIN from client")
                self.close_connection()
                self.close()
            elif segment.packet_type() == "DATA": 
                data = getattr(segment, 'data')
                self.send_data_ack(segment)
                if getattr(segment, 'seq_nr') == self.exp_seq_nr:
                    self.data_collection.append(data)
                    self.exp_seq_nr += 1
                else:
                    seq_nr = getattr(segment, 'seq_nr')
                    entry = {str(seq_nr) : segment}
                    self.segment_buffer.update(entry)
            else:
                print("Uknown packet type (", segment.packet_type(), ") or sequence number")

    # Wait for the client to initiate a three-way handshake
    def accept(self):
        self.state = State.LISTEN
        '''start update_buffer_thread()'''

    # Send any incoming data to the application layer
    def recv(self, output_file_path):
        self.data_list_to_file(output_file_path)

    # Clean up any state
    def close(self):
        self._lossy_layer.destroy()
    
    # Acknowledges the intitiation of a handshake with the client
    def handshake_response_thread(self, segment):
        seq_nr = randint(0,65535) - segment.get_seq_nr()
        ack_nr = segment.get_seq_nr() + 1
        segment.up_seq_nr(seq_nr)
        segment.up_ack_nr(ack_nr)
        self.hndsh_seq_nr = segment.get_seq_nr()
        segment.set_flags(ACK=True, SYN=True, FIN=False)
        send_segment = segment.pack()
        self._lossy_layer.send_segment(send_segment)
        self.state = State.SYN_ACK_SEND
        while True: # as long as no ACK handshake segment is received
            time.sleep(self.timeout/1000)
            if (self.state != State.HNDSH_COMP):
                self._lossy_layer.send_segment(send_segment)
            else:
                break
    
    #  
    def close_connection(self):
        segment = TCPpacket()
        segment.set_flags(ACK=True, SYN=False, FIN=True)
        send_segment = segment.pack()
        self._lossy_layer.send_segment(send_segment)
        
    # Send acknowledgement of a data-type segment.
    def send_data_ack(self, segment):
        segment.remove_data()
        old_ack_nr = getattr(segment, 'ack_nr')
        segment.up_ack_nr(getattr(segment, 'seq_nr') - old_ack_nr)
        segment.set_flags(ACK=True, SYN=False, FIN=False)
        send_segment = segment.pack()
        self._lossy_layer.send_segment(send_segment)
        self.close()
    
    # Continuously searches the buffer for the next in order segment.
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
                continue

    # Converts the list of bytesblocks back into a file    
    def data_list_to_file(self, output_file_path):
        print("data_collection:", self.data_collection)   
        for data_segment in self.data_collection:    
            with open(output_file_path, "ab") as binary_file:
                binary_file.write(data_segment)
        return 