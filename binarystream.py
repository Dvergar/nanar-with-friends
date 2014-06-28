from struct import *


class BinaryStream:
    def __init__(self, base_stream):
        self.base_stream = base_stream
        self.pos = 0

    def read_byte(self):
        return self.unpack('b')

    def read_bytes(self, length):
        return self.base_stream[self.pos:self.pos + length]

    def read_char(self):
        return self.unpack('b')

    def read_uchar(self):
        return self.unpack('B')

    def read_bool(self):
        return self.unpack('?')

    def read_int16(self):
        return self.unpack('h', 2)

    def read_uint16(self):
        return self.unpack('H', 2)

    def read_int32(self):
        return self.unpack('i', 4)

    def read_uint32(self):
        return self.unpack('I', 4)

    def read_int64(self):
        return self.unpack('q', 8)

    def read_uint64(self):
        return self.unpack('Q', 8)

    def read_float(self):
        return self.unpack('f', 4)

    def read_double(self):
        return self.unpack('d', 8)

    def read_string(self):
        length = self.read_uint16()
        return self.unpack(str(length) + 's', length)

    def unpack(self, fmt, length = 1):
        data = unpack('!' + fmt, self.read_bytes(length))[0]
        self.pos += length
        return data

    # def writeBytes(self, value):
    #     self.base_stream.write(value)

    # def writeChar(self, value):
    #     self.pack('c', value)

    # def writeUChar(self, value):
    #     self.pack('C', value)

    # def writeBool(self, value):
    #     self.pack('?', value)

    # def writeInt16(self, value):
    #     self.pack('h', value)

    # def writeUInt16(self, value):
    #     self.pack('H', value)

    # def writeInt32(self, value):
    #     self.pack('i', value)

    # def writeUInt32(self, value):
    #     self.pack('I', value)

    # def writeInt64(self, value):
    #     self.pack('q', value)

    # def writeUInt64(self, value):
    #     self.pack('Q', value)

    # def writeFloat(self, value):
    #     self.pack('f', value)

    # def writeDouble(self, value):
    #     self.pack('d', value)

    # def writeString(self, value):
    #     length = len(value)
    #     self.writeUInt16(length)
    #     self.pack(str(length) + 's', value)

    # def pack(self, fmt, data):
    #     return self.writeBytes(pack(fmt, data))
