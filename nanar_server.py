import select
import socket
import struct
import time
from twisted.internet.protocol import Factory
from twisted.protocols.basic import LineReceiver
from twisted.internet import reactor
from twisted.internet.task import LoopingCall

from binarystream import BinaryStream


MOVIE_TIME = 0
PING = 1
PLAYPAUSE = 2
MESSAGE = 3


class Connection(LineReceiver):

    def __init__(self, clients):
        self.clients = clients
        self.pings = []
        self.ping_check_time = time.time()

    def connectionMade(self):
        print "connectionMade"
        self.clients.append(self)
        lc = LoopingCall(self.ping_update)
        lc.start(0.2)

    def connectionLost(self, reason):
        print "connectionLost"
        self.clients.remove(self)

    def lineReceived(self, line):
        self.process_data(line)

    def ping_update(self):
        # print "ping_update (broadcast)"
        self.broadcast(self.get_datas_ping())
        self.ping_check_time = time.time()

    def broadcast(self, data, exception=None):
        # print "broadcast"
        for client in self.clients:
            if client is exception: continue
            client.sendLine(data)

    def process_data(self, data):
        bs = BinaryStream(data)

        msgtype = bs.read_byte()

        if msgtype == MESSAGE:
            print "MESSAGE"
            msg = bs.read_string()
            self.broadcast(self.get_datas_message(msg))

        elif msgtype == PLAYPAUSE:
            print "PLAYPAUSE"
            self.broadcast(self.get_datas_playpause(), self)

        elif msgtype == MOVIE_TIME:
            print "MOVIE_TIME"
            t = bs.read_int32()

            # broadcast
            for client in self.clients:
                if client is self: continue
                new_t = self.ping / 2 + client.ping / 2 + t
                print "new_t", new_t
                client.sendLine(self.get_datas_slider_update(new_t))

        elif msgtype == PING:
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
