from btcp.btcp_socket import BTCPSocket
from btcp.lossy_layer import LossyLayer
from btcp.constants import *
from btcp.packet import TCPpacket
import btcp.packet, time, threading
from concurrent.futures import ThreadPoolExecutor
from random import randint
from btcp.state import State

# bTCP client socket
# A client application makes use of the services provided by bTCP by calling connect, send, disconnect, and close
class BTCPClientSocket(BTCPSocket):
    def __init__(self, window, timeout):
        super().__init__(window, timeout)
        self.window = window
        self.timeout = timeout
        self.termination_count = 5
        self.thread_executor = ThreadPoolExecutor(max_workers=window)
        self._lossy_layer = LossyLayer(self, CLIENT_IP, CLIENT_PORT, SERVER_IP, SERVER_PORT)
        self.state = State.CLOSED
        self.hndsh_seq_nr = 0 # gets set after connect()
        self.hndsh_ack_nr = 0 # gets set after connect()
        self.seq_nr = 0
        
    # Called by the lossy layer from another thread whenever a segment arrives. 
    def lossy_layer_input(self, segment):
        segment = btcp.packet.unpack_from_socket(segment)
        segment_type = segment.packet_type()
        if segment_type == "SYN-ACK" and getattr(segment, 'ack_nr') == self.hndsh_seq_nr + 1:
            self.state = State.SYN_ACK_RECVD
            self.thread_executor.submit(self.handshake_ack_thread, segment)
        elif segment_type == "FIN_ACK":
            # handle closing of socket
            pass
        elif segment_type == "ACK":
            # remove segment corresponding to this ACK from window
            pass
        else:
            pass

    # Initiate a three-way handshake with the server.
    def connect(self):
        self.thread_executor.submit(self.con_establish_thread)
        self.state = State.SYN_SEND

    # Send data originating from the application in a reliable way to the server
    def send(self, data):
        #segments_list = load_file(data)
        # TODO: add functions to send data
        pass

    # Perform a handshake to terminate a connection
    def disconnect(self):
        pass

    # Clean up any state
    def close(self):
        self._lossy_layer.destroy()
    
    # Send the response to the server's ACK of the handshake.
    def handshake_ack_thread(self, segment):
        seq_nr = segment.get_ack_nr()
        ack_nr = segment.get_seq_nr() + 1
        segment.up_seq_nr(seq_nr - (ack_nr -1)) # remove old seq_nr (which is now ack_nr) and replace by new seq_nr
        segment.up_ack_nr(ack_nr - seq_nr + 0) # remove old ack_nr (which is now seq_nr) and replace by new ack_nr
        segment.set_flags(True, False, False) # set ACK flag
        send_segment = segment.pack()
        self._lossy_layer.send_segment(send_segment)
    
    # Runnable function to establish a connection with the server
    def con_establish_thread(self):
        seq_nr = randint(0,65535) # random 16-bit integer
        self.hndsh_seq_nr = seq_nr
        segment = TCPpacket(seq_nr)
        segment.set_flags(False, True, False) # set SYN flag
        send_segment = segment.pack()
        self._lossy_layer.send_segment(send_segment)
        self._lossy_layer.send_segment(send_segment)
        while True:
            time.sleep(self.timeout/1000)
            if self.state != State.SYN_ACK_RECVD:
                self._lossy_layer.send_segment(send_segment)
            else:
                self.state = State.HNDSH_COMP
                break

    # Loading file
    # TODO: go one folder upwards to read the file
    def load_file(self, file):
        """Loads the file and converts it into a list of segments that are ready to be send"""
        rawbytes = self.read_file(file)
        data_list = self.rawbytes_to_sections(rawbytes)
        segments_list = self.file_data_to_segments_list(data_list)
        return segments_list
    
    def read_file(self, file):
        """ Reads the file as bytes """
        with open(file, "rb") as binary_file:
            # Read the whole file at once
            rawbytes = binary_file.read()
            return rawbytes

    # TODO: add padding to final packet    
    def rawbytes_to_sections(self, rawbytes):
        """
            Takes the bytes and divides these into chunks of 1008 bytes (except the
            last one which is probably smaller). These chunks are placed into a list
            for easy access in the rest of the program.
        """
        data_sections = []
        while len(rawbytes) > 0:
            if len(rawbytes) >= 1008:
                data_sections.append(rawbytes[:1008])
                rawbytes = rawbytes[1008:]
            else:
                data_sections.append(rawbytes)
                rawbytes = b''
        return data_sections
        
    def file_data_to_segments_list(self, file_data):
        """
            Takes the list of file_data (in chunks of 1008 bytes) and creates
            segments for each of those chunks. These segments are put in the
            segments_list and this segments_list is returned.
        """    
        segments_list = []
        for data in file_data:
            segment = TCPpacket(seq_nr=self.seq_nr, ack_nr=self.ack_nr, window=self.window)
            segment.set('data', data)
            segment.up_seq_nr(segment.data_length)
            seq_nr += segment.data_length  
            segments_list.append(segment)
        return segments_list    