import select
import socket
import struct
import time
from twisted.internet.protocol import Factory
from twisted.protocols.basic import LineReceiver
from twisted.internet import reactor
from twisted.internet.task import LoopingCall

MOVIE_TIME = 0
PING = 1
PLAYPAUSE = 2
MESSAGE = 3


class BinaryStream:
    def __init__(self):
        self.byte_struct = struct.Struct("!b")
        self.ubyte_struct = struct.Struct("!B")
        self.int_struct = struct.Struct("!i")
        self.short_struct = struct.Struct("!h")
        self.ushort_struct = struct.Struct("!H")
        self.float_struct = struct.Struct("!f")

    def put_data(self, data):
        self.data = data
        self.len_data = len(data)
        self.pos = 0

    def read_data_left(self):
        return self.data[self.pos:]

    def read_byte(self):
        size = 1
        byte = self.data[self.pos:self.pos + size]
        byte, = self.byte_struct.unpack(byte)
        self.pos += size
        return byte

    def read_ubyte(self):
        size = 1
        byte = self.data[self.pos:self.pos + size]
        byte, = self.ubyte_struct.unpack(byte)
        self.pos += size
        return byte

    def read_float(self):
        size = 4
        _float = self.data[self.pos:self.pos + size]
        _float, = self.float_struct.unpack(_float)
        self.pos += size
        return _float

    def read_int(self):
        size = 4
        _int = self.data[self.pos:self.pos + size]
        _int, = self.int_struct.unpack(_int)
        self.pos += size
        return _int

    def read_short(self):
        size = 2
        short = self.data[self.pos:self.pos + size]
        short, = self.short_struct.unpack(short)
        self.pos += size
        return short

    def read_ushort(self):
        size = 2
        ushort = self.data[self.pos:self.pos + size]
        ushort, = self.ushort_struct.unpack(ushort)
        self.pos += size
        return ushort

    def read_UTF(self):
        print "UTF", repr(self.data)
        size = 2
        length = self.data[self.pos:self.pos + size]
        length, = self.short_struct.unpack(length)
        self.pos += size
        string = self.data[self.pos:self.pos + length]
        string, = struct.unpack("!" + str(length) + "s", string)
        self.pos += length
        return string

    def working(self):
        if self.pos == self.len_data:
            return False
        else:
            return True

bs = BinaryStream()


class Connection(LineReceiver):

    def __init__(self, clients):
        self.clients = clients
        self.pings = []
        self.ping_check_time = time.time()

    def connectionMade(self):
        print "connectionMade"
        self.clients.append(self)
        lc = LoopingCall(self.ping_update)
        lc.start(1)

    def connectionLost(self, reason):
        print "connectionLost"
        self.clients.remove(self)

    def lineReceived(self, line):
        self.process_data(line)

    def ping_update(self):
        print "ping_update (broadcast)"
        self.broadcast(self.get_datas_ping())
        self.ping_check_time = time.time()

    def broadcast(self, data, exception=None):
        for client in self.clients:
            if client is exception: continue
            client.sendLine(data)

    def process_data(self, data):
        bs.put_data(data)
        while bs.working():
            msgtype = bs.read_byte()

            if msgtype == MESSAGE:
                print "MESSAGE"
                msg = bs.read_UTF()
                self.broadcast(self.get_datas_message(msg))

            elif msgtype == PLAYPAUSE:
                print "PLAYPAUSE"
                self.broadcast(self.get_datas_playpause(), self)

            elif msgtype == MOVIE_TIME:
                print "MOVIE_TIME"
                t = bs.read_int()

                # broadcast
                for client in self.clients:
                    # if client is self: continue
                    new_t = self.ping / 2 + client.ping / 2 + t
                    print "new_t", new_t
                    client.sendLine(self.get_datas_slider_update(new_t))

            elif msgtype == PING:
                print "PING"
                self.pings.append(time.time() - self.ping_check_time)
                if len(self.pings) > 50:
                    del self.pings[0]

    @property
    def ping(self):
        return (sum(self.pings) / len(self.pings)) * 1000

    def get_datas_slider_update(self, pos):
        return struct.pack("!Bi", MOVIE_TIME, pos)

    def get_datas_ping(self):
        return struct.pack("!B", PING)

    def get_datas_playpause(self):
        return struct.pack("!B", PLAYPAUSE)

    def get_datas_message(self, msg):
        return struct.pack("!BH" + str(len(msg)) + "s", MESSAGE, len(msg), msg)


class ServerFactory(Factory):

    def __init__(self):
        self.clients = []

    def buildProtocol(self, addr):
        return Connection(self.clients)


if __name__ == "__main__":
    reactor.listenTCP(1337, ServerFactory())
    reactor.run()
