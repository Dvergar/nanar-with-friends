import vlc
import time
import select
import socket
import sys
import struct
from Tkinter import *


POS = 0


conn_type = sys.argv[1]
if len(sys.argv) == 3:
    host = sys.argv[2]
else:
    host = '127.0.0.1'


class BinaryStream:
    def __init__(self):
        self.byte_struct = struct.Struct("!b")
        self.ubyte_struct = struct.Struct("!B")
        self.int_struct = struct.Struct("!i")
        self.short_struct = struct.Struct("!h")
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
        byte = self.data[self.pos:self.pos + size]
        byte, = self.float_struct.unpack(byte)
        self.pos += size
        return byte

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


class Connection:
    def __init__(self, app, conn_type, host='127.0.0.1'):
        self.app = app
        port = 50000
        port = 1337
        self.size = 65536
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        print "Connection Type detected :", conn_type
        if conn_type == "server":
            backlog = 5
            self.clients = []
            self.server.bind((host, port))
            self.server.listen(backlog)
            self.update = self.server_update
            self.send = self.server_send
        elif conn_type == "client":
            self.server.connect((host, port))
            self.update = self.client_update
            self.send = self.client_send
            # self.server.send("hello i am client")
        self.input = [self.server]

    def update(self):
        return NotImplemented

    def send(self):
        return NotImplemented

    def client_update(self):
        # print "client_update"
        inready, outready, exceptready = select.select(self.input, [], [], 0)
        if len(inready) == 1:
            data = self.server.recv(self.size)
            if data:
                self.client_on_data(data)

    def server_update(self):
        # print "server_update"
        inready, outready, exceptready = select.select(self.input, [], [], 0)

        for s in inready:
            if s == self.server:
                client, address = self.server.accept()
                self.input.append(client)
                self.clients.append(client)
                # msg = "hello"
                # data = struct.pack("H5s", len(msg), msg)
                # client.sendall("hello i am server")
                print "Connection from", address
            else:
                data = s.recv(self.size)
                if data:
                    self.server_on_data(s, data)
                else:
                    print "close"
                    s.close()
                    self.input.remove(s)
                    self.clients.remove(s)

    def server_on_data(self, s, data):
        print s
        print data
        self.server_send(data)
        self.process_data(data)

    def client_on_data(self, data):
        print data
        self.process_data(data)

    def server_send(self, data):
        for client in self.clients:
            # print "send to client", data
            client.sendall(data)

    def client_send(self, data):
        self.server.sendall(data)

    def process_data(self, data):
        bs.put_data(data)
        print "datalen", len(data), repr(data)
        while bs.working():
            msgtype = bs.read_byte()
            print "msgtype", msgtype
            if msgtype == POS:
                # print "len", len(data)
                pos = bs.read_float()
                self.app.updateScaleValueFromNet(pos)


class App:
    def __init__(self):
        self.loop_rate = 10
        self.conn = Connection(self, conn_type, host)
        self.start_video()
        self.UI_init()

    def start_video(self):
        self.p = vlc.MediaPlayer(
            'C:/Users/Caribou/Dropbox/Public/test_video.avi')
        self.p.audio_set_volume(0)
        self.p.play()

    def UI_init(self):
        self.root = Tk()
        self.scale = Scale(
            self.root, from_=0, to=100,
            orient=HORIZONTAL,
            command=self.updateScaleValue)
        self.scale.config(
            width=50,
            length=1000,
            resolution=0.001,
            label=conn_type)
        self.scale.pack()
        self.root.after(self.loop_rate, self.task)
        self.root.mainloop()

    def updateScaleValue(self, _):
        pos = self.scale.get() / 10
        self.p.set_position(pos)
        posmsg = struct.pack("!Bf", POS, pos)
        self.conn.send(posmsg)

    def updateScaleValueFromNet(self, pos):
        self.p.set_position(pos)

    def task(self):
        self.conn.update()
        self.root.after(self.loop_rate, self.task)


App()
