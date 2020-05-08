from btcp.btcp_socket import BTCPSocket
from btcp.lossy_layer import LossyLayer
from btcp.constants import *
from btcp.packet import TCPpacket
from btcp.packet import up_nr
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
        self.windowLock = threading.Lock()
        self.segment_buffer = {}    # segments that are received out of order
        # self.acks_list = [] # list of all received ACKS
        self.timeout = timeout
        self.termination_count = 5
        self.thread_executor = ThreadPoolExecutor(max_workers=window)
        self._lossy_layer = LossyLayer(self, CLIENT_IP, CLIENT_PORT, SERVER_IP, SERVER_PORT)
        self.state = State.CLOSED
        self.seq_nr = 0 # gets set after connect()
        self.ack_nr = 0 # gets set after connect()
        
    # Called by the lossy layer from another thread whenever a segment arrives. 
    def lossy_layer_input(self, segment):
        segment = btcp.packet.unpack_from_socket(segment)
        segment_type = segment.packet_type()
        if segment_type == "SYN-ACK" and getattr(segment, 'ack_nr') == self.hndsh_seq_nr + 1:
            self.state = State.SYN_ACK_RECVD
            self.thread_executor.submit(self.handshake_ack_thread, segment)
        elif segment_type == "FIN_ACK":
            # TODO: handle closing of socket
            self.state = State.HNDSH_COMP
            pass
        elif segment.pack_type() == "ACK":     
            segment_ack_nr = getattr(segment, 'ack_nr')            
            self.segment_buffer.updateentry = {str(segment_ack_nr) : segment}
        else:
            pass

    # Initiate a three-way handshake with the server.
    def connect(self):
        self.thread_executor.submit(self.con_establish_thread)
        self.state = State.SYN_SEND

    # Send data originating from the application in a reliable way to the server
    def send(self, data):
        segments_list = self.load_file(data)
        self.data_transfer(segments_list)
        # TODO: add functions to send data

    # Perform a handshake to terminate a connection
    def disconnect(self):
        self.thread_executor.submit(self.con_close_thread)
            # move .close() to thread function
        self.close()

    # Clean up any state
    def close(self):
        self.thread_executor.shutdown(wait=True)
        self._lossy_layer.destroy()
        print("CLIENT CLOSED")
    
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
        self.seq_nr = seq_nr
        segment = TCPpacket(seq_nr)
        segment.set_flags(False, True, False) # set SYN flag
        send_segment = segment.pack()
        self._lossy_layer.send_segment(send_segment)
        while True:
            time.sleep(self.timeout/1000)
            if self.state != State.SYN_ACK_RECVD:
                self._lossy_layer.send_segment(send_segment)
            else:
                self.state = State.HNDSH_COMP
                break
            
    # Runnable function to close the connection with the server
    def con_close_thread(self):
        segment = TCPpacket()
        segment.set_flags(False, False, True)
        send_segment = segment.pack()
        self._lossy_layer.send_segment(send_segment)
        while True:
            time.sleep(self.timeout/1000)
            if self.state != State.FIN_ACK_RECVD and self.termination_count > 0:
                self._lossy_layer.send_segment(send_segment)
                self.termination_count -= 1
            else:
                self.state = State.CLOSED
                self.close()
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

    # TODO: add padding to final segment    
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
            self.seq_nr = up_nr(self.seq_nr, segment.data_length)
            segments_list.append(segment)
        return segments_list    

    def packet_thread(self, segment):
        """
            First sends a packet and then checks the list of acks for 
            [timeout] seconds to see if the corresponding ack has been received,
            if not, a timeout is triggered. This timeout causes the packet to 
            be resend
        """
        ack_received = False
        
        while not ack_received:
            self._lossy_layer.send_segment(segment.pack())
            ack_nr_segment = str(getattr(segment, 'syn_nr') + getattr(segment, 'data_length'))
            time.sleep(self.timeout/1000) # wait for incomming ack
            if self.segment_buffer[ack_nr_segment]: #ack received
                self.windowLock.acquire()
                self.window += 1
                self.windowLock.release()
                ack_received = True
            else:
                continue      

    def data_transfer(self, segments_list):
        """
            Sends the file from the client to the server by distributing the
            data over packets.
        """
        # acks_thread = threading.Thread(target=self.recv_acks_thread)
        # acks_thread.start()
        
        window = self.window
        thread_list = [threading.Thread(target=self.packet_thread, args= (segment,)) for segment in segments_list]
        sending_list = thread_list
        while (len(sending_list) > 0 ): # keeps looping until the list is empty
            # when there are less packets remaining to be send then the window size
            sending_list = sending_list
            if len(sending_list) <= window:
                for t in sending_list:
                    self.windowLock.acquire()
                    self.window -= 1
                    self.windowLock.release()
                    t.start()
                sending_list = []
            # when there are more packets remaining to be send then the window size
            else:
                number_of_threads = window
                for t in sending_list[:number_of_threads]: # number_of_packets could be window size
                    self.windowLock.acquire()
                    window -= 1
                    self.windowLock.release()
                    t.start()
                sending_list = sending_list[number_of_threads:]
        
        for thread in thread_list:
            thread.join()
        self.transfer_complete = True
        # acks_thread.join()
        # print("Length segments list: ", len(packet_list))
        print("Data transmission is finished")