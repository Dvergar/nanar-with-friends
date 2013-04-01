import vlc
import time
import select
import socket
import sys
import struct
from PyQt4 import QtGui, QtCore

MOVIE_TIME = 0
PING = 1

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


class Connection:
    def __init__(self, app, conn_type, host='127.0.0.1'):
        self.app = app
        self.type = conn_type
        port = 50000
        port = 1337
        self.size = 65536
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        print "Connection Type detected :", conn_type
        if conn_type == "server":
            backlog = 5
            self.clients = []
            self.pings = {}
            self.server.bind((host, port))
            self.server.listen(backlog)
            self.update = self.server_update
            self.send = self.server_send
            self.ping_check_time = time.time() - 42
        elif conn_type == "client":
            self.server.connect((host, 4242))
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
                self.pings[client] = []
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
                    del self.pings[client]

        if time.time() - self.ping_check_time > 0.1:
            for client in self.clients:
                p = Ping(client)
                client.sendall(self.get_datas_ping(p.id))
            # self.server_send()

    def server_on_data(self, s, data):
        # self.server_send(data)
        self.process_data(data, s)

    def client_on_data(self, data):
        self.process_data(data)

    def server_send(self, data):
        for client in self.clients:
            # print "send to client", data
            client.sendall(data)

    def client_send(self, data):
        self.server.sendall(data)

    def send_movie_time(self, t):
        if self.type == "server":
            for client in self.clients:
                client_pings = self.pings[client]
                avg_ping = sum(client_pings) / len(client_pings)
                new_t = t + avg_ping / 2
                client.sendall(self.get_datas_slider_update(new_t))
        elif self.type == "client":
            self.send(self.get_datas_slider_update(t))

    def process_data(self, data, client=None):
        bs.put_data(data)
        while bs.working():
            msgtype = bs.read_byte()

            if msgtype == MOVIE_TIME:
                # print "len", len(data)
                t = bs.read_int()
                if self.type == "client":
                    self.app.change_pos_from_net(t)  # t already smoothed
                elif self.type == "server":
                    client_pings = self.pings[client]
                    avg_ping = sum(client_pings) / len(client_pings)

                    # broadcast
                    for bclient in self.clients:
                        if bclient == client:
                            continue
                        b_avg_ping = sum(client_pings) / len(client_pings)
                        new_t = avg_ping / 2 + b_avg_ping / 2 + t
                        bclient.sendall(self.get_datas_slider_update(new_t))

                    # update local
                    self.app.change_pos_from_net(t + avg_ping / 2)

            if msgtype == PING:
                _id = bs.read_int()
                if self.type == "client":
                    self.send(self.get_datas_ping(_id))
                elif self.type == "server":
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


class NanarPlayer(QtGui.QMainWindow):
    def __init__(self, master=None):
        QtGui.QMainWindow.__init__(self, master)

        self.loop_rate = 10
        self.conn = Connection(self, conn_type, host)
        self.start_loop()

        self.setWindowTitle("NanarPlayer")

        # creating a basic vlc instance
        self.instance = vlc.Instance()
        # creating an empty vlc media player
        self.p = self.instance.media_player_new()

        self.createUI()
        self.isPaused = False
        self.slider_is_moving = False
        self.slider_pos = 0
        self.OpenFile("C:/Users/Caribou/Dropbox/Public/test_video.avi")
        self.p.audio_set_volume(0)

    def start_loop(self):
        self.timer2 = QtCore.QTimer()
        self.timer2.timeout.connect(self.loop)
        self.timer2.start(10)

    def change_pos(self):
        print "LOCAL pos", self.slider_pos
        k = self.p.get_length() / 1000.
        time = k * self.slider_pos
        print "time", time

        self.set_slider_position(time)
        self.conn.send_movie_time(time)

    def change_pos_from_net(self, time):
        print "NET pos", time
        self.set_slider_position(time)

    def set_slider_position(self, time):
        k = self.p.get_length() / 1000.
        pos = time / k
        print "new pos", pos
        pos = pos / 1000.
        if pos >= 1.0:
            pos = 0.99
        print "setpos", pos
        self.p.set_position(pos)

    def loop(self):
        self.conn.update()

    def on_slider_move(self, pos):
        self.slider_is_moving = True
        self.slider_pos = pos

    def createUI(self):
        self.widget = QtGui.QWidget(self)
        self.setCentralWidget(self.widget)

        # In this widget, the video will be drawn
        self.videoframe = QtGui.QFrame()
        self.palette = self.videoframe.palette()
        self.palette.setColor(
            QtGui.QPalette.Window,
            QtGui.QColor(0, 0, 0))
        self.videoframe.setPalette(self.palette)
        self.videoframe.setAutoFillBackground(True)

        self.positionslider = QtGui.QSlider(QtCore.Qt.Horizontal, self)
        self.positionslider.setToolTip("Position")
        self.positionslider.setMaximum(1000)
        self.positionslider.setTracking(False)
        self.connect(self.positionslider,
                     QtCore.SIGNAL("sliderReleased()"), self.change_pos)
        self.connect(self.positionslider,
                     QtCore.SIGNAL("sliderMoved(int)"), self.on_slider_move)

        self.hbuttonbox = QtGui.QHBoxLayout()
        self.playbutton = QtGui.QPushButton("Play")
        self.hbuttonbox.addWidget(self.playbutton)
        self.connect(self.playbutton, QtCore.SIGNAL("clicked()"),
                     self.PlayPause)

        self.stopbutton = QtGui.QPushButton("Stop")
        self.hbuttonbox.addWidget(self.stopbutton)
        self.connect(self.stopbutton, QtCore.SIGNAL("clicked()"),
                     self.Stop)

        self.hbuttonbox.addStretch(1)
        self.volumeslider = QtGui.QSlider(QtCore.Qt.Horizontal, self)
        self.volumeslider.setMaximum(100)
        self.volumeslider.setValue(self.p.audio_get_volume())
        self.volumeslider.setToolTip("Volume")
        self.hbuttonbox.addWidget(self.volumeslider)
        self.connect(self.volumeslider,
                     QtCore.SIGNAL("valueChanged(int)"),
                     self.setVolume)

        self.vboxlayout = QtGui.QVBoxLayout()
        self.vboxlayout.addWidget(self.videoframe)
        self.vboxlayout.addWidget(self.positionslider)
        self.vboxlayout.addLayout(self.hbuttonbox)

        self.widget.setLayout(self.vboxlayout)

        open = QtGui.QAction("&Open", self)
        self.connect(open, QtCore.SIGNAL("triggered()"), self.OpenFile)
        exit = QtGui.QAction("&Exit", self)
        self.connect(exit, QtCore.SIGNAL("triggered()"), sys.exit)
        menubar = self.menuBar()
        filemenu = menubar.addMenu("&File")
        filemenu.addAction(open)
        filemenu.addSeparator()
        filemenu.addAction(exit)

        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(200)
        self.connect(self.timer, QtCore.SIGNAL("timeout()"),
                     self.updateUI)

    def PlayPause(self):
        if self.p.is_playing():
            self.p.pause()
            self.playbutton.setText("Play")
            self.isPaused = True
        else:
            if self.p.play() == -1:
                self.OpenFile()
                return
            self.p.play()
            self.playbutton.setText("Pause")
            self.timer.start()
            self.isPaused = False

    def Stop(self):
        self.p.stop()
        self.playbutton.setText("Play")

    def OpenFile(self, filename=None):
        if filename is None:
            filename = QtGui.QFileDialog.getOpenFileName(self, "Open File", user.home)
        if not filename:
            return

        # create the media
        self.media = self.instance.media_new(unicode(filename))
        # put the media in the media player
        self.p.set_media(self.media)

        # parse the metadata of the file
        self.media.parse()

        # set the title of the track as window title
        self.setWindowTitle(self.media.get_meta(0))

        # the media player has to be 'connected' to the QFrame
        # (otherwise a video would be displayed in it's own window)
        # this is platform specific!
        # you have to give the id of the QFrame (or similar object) to
        # vlc, different platforms have different functions for this
        if sys.platform == "linux2": # for Linux using the X Server
            self.p.set_xwindow(self.videoframe.winId())
        elif sys.platform == "win32": # for Windows
            self.p.set_hwnd(self.videoframe.winId())
        elif sys.platform == "darwin": # for MacOS
            self.p.set_agl(self.videoframe.windId())
        self.PlayPause()

        # Ugly but fuck callbacks
        while self.p.get_length() == 0:
            pass
        self.movie_length = self.p.get_length()
        print "movie_lenght", self.movie_length

    def setVolume(self, Volume):
        self.p.audio_set_volume(Volume)

    def setPosition(self, position):
        self.p.set_position(position / 1000.0)

    def updateUI(self):
        """updates the user interface"""
        # setting the slider to the desired position
        if not self.slider_is_moving:
            self.positionslider.setValue(self.p.get_position() * 1000)

        if not self.p.is_playing():
            # no need to call this function if nothing is played
            self.timer.stop()
            if not self.isPaused:
                # after the video finished, the play button stills shows
                # "Pause", not the desired behavior of a media player
                # this will fix it
                self.Stop()

if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    nanar_player = NanarPlayer()
    nanar_player.show()
    nanar_player.resize(640, 480)
    # if sys.argv[1:]:
    #     nanar_player.OpenFile(sys.argv[1])
    sys.exit(app.exec_())
