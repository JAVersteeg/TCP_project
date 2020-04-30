from enum import Enum

class State(Enum):
    CLOSED = 0
    LISTEN = 1
    SYN_SEND = 2
    SYN_RECVD = 3
    ESTABLISHED = 4
    FIN_WAIT_1 = 5
    FIN_WAIT_2 = 6
    CLOSING = 7
    TIME_WAIT = 8
    CLOSE_WAIT = 9
    LAST_ACK = 10