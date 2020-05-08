from enum import Enum

class State(Enum):
    CLOSED = 0
    LISTEN = 1
    SYN_SEND = 2
    SYN_ACK_SEND = 15
    SYN_RECVD = 3
    SYN_ACK_RECVD = 12
    FIN_RECVD = 14
    FIN_ACK_RECVD = 13
    HNDSH_COMP = 11
    ESTABLISHED = 4
    FIN_WAIT_1 = 5
    FIN_WAIT_2 = 6
    CLOSING = 7
    TIME_WAIT = 8
    CLOSE_WAIT = 9
    LAST_ACK = 10