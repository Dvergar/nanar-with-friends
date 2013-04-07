import select
import socket
import struct
import time


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


class Ping:
    pending = {}
    _id = 0

    def __init__(self, client):
        self.id = Ping._id
        self.client = client
        if not client in self.pending:
            self.pending[client] = {}
        self.pending[client][self.id] = self
        self.time = time.time()
        Ping._id += 1

    def get_value(self):
        del self.pending[self.client][self.id]
        return time.time() * 1000 - self.time * 1000


class Server:
    def __init__(self, host='127.0.0.1'):
        port = 1337
        self.buff_datas = ""
        self.reading = False
        self.LEN_MSG = 0
        self.size = 65536
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        backlog = 5
        self.clients = []
        self.pings = {}
        self.server.bind((host, port))
        self.server.listen(backlog)
        self.ping_check_time = time.time() - 42

        self.input = [self.server]
        self.update()

    def update(self):
        while True:
            inready, outready, exready = select.select(self.input, [], [], 0)

            for s in inready:
                if s == self.server:
                    client, address = self.server.accept()
                    self.input.append(client)
                    self.clients.append(client)
                    self.pings[client] = []
                    print "Connection from", address
                else:
                    datas = s.recv(self.size)
                    if datas:
                        self.buff_datas += datas
                        if not self.reading:
                            if len(self.buff_datas) > 2:
                                self.LEN_MSG, = struct.unpack(
                                    "!H",
                                    self.buff_datas[0:2])
                                self.buff_datas = self.buff_datas[2:]
                                self.reading = True
                        if self.reading:
                            if len(self.buff_datas) >= self.LEN_MSG:
                                # print "SERVER READABLE"
                                # use bytesIo instead
                                goot_data = self.buff_datas[:self.LEN_MSG]
                                self.buff_datas = (self.buff_datas[
                                                   self.LEN_MSG:])
                                self.on_data(s, goot_data)
                                self.reading = False
                    else:
                        print "close"
                        s.close()
                        self.input.remove(s)
                        self.clients.remove(s)
                        del self.pings[client]

            if time.time() - self.ping_check_time > 1:
                for client in self.clients:
                    p = Ping(client)
                    self.send(self.get_datas_ping(p.id), client)
                self.ping_check_time = time.time()

    def on_data(self, s, data):
        # self.server_send(data)
        self.process_data(data, s)

    def send(self, data, client):
        client.send(struct.pack("!H", len(data)))
        client.send(data)

    def process_data(self, data, client=None):
        bs.put_data(data)
        while bs.working():
            msgtype = bs.read_byte()

            if msgtype == MESSAGE:
                msg = bs.read_UTF()
                for bclient in self.clients:
                    self.send(self.get_datas_message(msg), bclient)

            elif msgtype == PLAYPAUSE:
                for bclient in self.clients:
                    if bclient == client:
                        continue
                    self.send(self.get_datas_playpause(), bclient)

            elif msgtype == MOVIE_TIME:
                t = bs.read_int()

                client_pings = self.pings[client]
                avg_ping = sum(client_pings) / len(client_pings)

                # broadcast
                for bclient in self.clients:
                    b_avg_ping = sum(client_pings) / len(client_pings)
                    new_t = avg_ping / 2 + b_avg_ping / 2 + t
                    self.send(self.get_datas_slider_update(new_t), bclient)

            elif msgtype == PING:
                _id = bs.read_int()

                ping = Ping.pending[client][_id].get_value()
                client_pings = self.pings[client]
                if len(client_pings) > 50:
                    del client_pings[0]
                client_pings.append(ping)
                avg_ping = sum(client_pings) / len(client_pings)

    def get_datas_slider_update(self, pos):
        return struct.pack("!Bi", MOVIE_TIME, pos)

    def get_datas_ping(self, _id):
        return struct.pack("!Bi", PING, _id)

    def get_datas_playpause(self):
        return struct.pack("!B", PLAYPAUSE)

    def get_datas_message(self, msg):
        return struct.pack("!BH" + str(len(msg)) + "s", MESSAGE, len(msg), msg)


if __name__ == "__main__":
    Server()
