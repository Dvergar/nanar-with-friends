import vlc
import select
import socket
import sys
import struct
import user
from PyQt4 import QtGui, QtCore
import argparse


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


class Connection:
    def __init__(self, app, host='127.0.0.1'):
        self.app = app
        port = 1337
        self.buff_datas = ""
        self.reading = False
        self.LEN_MSG = 0
        self.size = 65536
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.connect((host, port))
        self.input = [self.server]

    def update(self):
        # print "client_update"
        inready, outready, exceptready = select.select(self.input, [], [], 0)
        if len(inready) == 1:
            datas = self.server.recv(self.size)
            if datas:
                # print "lendatas", len(datas)
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
                        # use bytesIo instead
                        goot_data = self.buff_datas[:self.LEN_MSG]
                        self.buff_datas = self.buff_datas[self.LEN_MSG:]
                        self.on_data(goot_data)
                        self.reading = False

    def on_data(self, data):
        self.process_data(data)

    def send(self, data):
        self.server.send(struct.pack("!H", len(data)))
        self.server.send(data)

    def send_movie_time(self, t):
        self.send(self.get_datas_slider_update(t))

    def send_playpause(self):
        self.send(self.get_datas_playpause())

    def send_message(self, msg):
        self.send(self.get_datas_message(msg))

    def process_data(self, data, client=None):
        bs.put_data(data)
        while bs.working():
            msgtype = bs.read_byte()

            if msgtype == MESSAGE:
                msg = bs.read_UTF()
                self.app.update_chat(msg)

            elif msgtype == PLAYPAUSE:
                self.app.play_pause()

            elif msgtype == MOVIE_TIME:
                t = bs.read_int()
                self.app.change_pos_from_net(t)  # t already smoothed

            elif msgtype == PING:
                _id = bs.read_int()
                self.send(self.get_datas_ping(_id))

    def get_datas_slider_update(self, pos):
        return struct.pack("!Bi", MOVIE_TIME, pos)

    def get_datas_ping(self, _id):
        return struct.pack("!Bi", PING, _id)

    def get_datas_playpause(self):
        return struct.pack("!B", PLAYPAUSE)

    def get_datas_message(self, msg):
        return struct.pack("!BH" + str(len(msg)) + "s", MESSAGE, len(msg), msg)


class NanarPlayer(QtGui.QMainWindow):
    def __init__(self, host, _input, master=None):
        QtGui.QMainWindow.__init__(self, master)
        self.setWindowTitle("NanarPlayer")

        # creating a basic vlc instance
        self.instance = vlc.Instance()
        # creating an empty vlc media player
        self.p = self.instance.media_player_new()

        # UI
        self.createUI()
        self.p.audio_set_volume(0)
        self.isPaused = False
        self.slider_is_moving = False
        self.slider_pos = 0

        # Net
        self.loop_rate = 10
        if host is not None:
            print "Connecting to...", host
            try:
                self.make_connection(host)
            except socket.error, (value, message):
                print "Connection problem !", message
                sys.exit(self)

        # File/stream
        if _input is not None:
            print "Opening :", _input
            self.OpenFile(_input)

    def make_connection(self, host):
        self.conn = Connection(self, host)
        self.timer2 = QtCore.QTimer()
        self.timer2.timeout.connect(self.conn.update)
        self.timer2.start(10)

    def change_pos(self):
        print "LOCAL pos", self.slider_pos
        k = self.p.get_length() / 1000.
        timee = k * self.slider_pos
        print "time", timee

        self.set_slider_position(timee)
        self.conn.send_movie_time(timee)

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
        # self.videoframe.setGeometry(20, 20, 100, 100)

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
                     self.GUI_play_pause)

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

        self.hinputchatbox = QtGui.QHBoxLayout()
        self.lenick = QtGui.QLineEdit()
        self.lechat = QtGui.QLineEdit()
        self.hinputchatbox.addWidget(self.lenick)
        self.hinputchatbox.addWidget(self.lechat, 3)

        self.te = QtGui.QTextEdit()
        self.te.setMaximumHeight(60)

        self.vboxlayout = QtGui.QVBoxLayout()
        self.vboxlayout.addWidget(self.videoframe, 2)
        self.vboxlayout.addWidget(self.positionslider)
        self.vboxlayout.addLayout(self.hbuttonbox)
        self.vboxlayout.addWidget(self.te)
        # self.vboxlayout.addWidget(self.le)
        self.vboxlayout.addLayout(self.hinputchatbox)

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
        self.connect(self.lechat, QtCore.SIGNAL("returnPressed(void)"),
                     self.run_command)

    def run_command(self):
        nick = str(self.lenick.text())
        if nick == "":
            nick = "abitbol"
        cmd = str(self.lechat.text())
        print cmd
        self.lechat.setText("")
        pretty_msg = nick + " : " + cmd
        # self.update_chat(pretty_msg)
        self.conn.send_message(pretty_msg)

    def update_chat(self, txt):
        self.te.append(txt)

    def GUI_play_pause(self):
        self.play_pause()
        self.conn.send_playpause()

    def play_pause(self):
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
            filename = QtGui.QFileDialog.getOpenFileName(self, "Open File",
                                                         user.home)
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
        if sys.platform == "linux2":  # for Linux using the X Server
            self.p.set_xwindow(self.videoframe.winId())
        elif sys.platform == "win32":  # for Windows
            self.p.set_hwnd(self.videoframe.winId())
        elif sys.platform == "darwin":  # for MacOS
            self.p.set_agl(self.videoframe.windId())
        self.play_pause()

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

    # if sys.argv[1:]:
    #     host = sys.argv[1]
    # else:
    #     host = "127.0.0.1"

    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input", help="give file or stream to read")
    parser.add_argument("-a", "--address", help="server ip address")
    args = parser.parse_args()

    nanar_player = NanarPlayer(args.address, args.input)
    nanar_player.show()
    nanar_player.resize(640, 480)
    # if sys.argv[1:]:
    #     nanar_player.OpenFile(sys.argv[1])
    sys.exit(app.exec_())
