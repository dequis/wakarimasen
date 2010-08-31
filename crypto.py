'''Module with misleading name for cryptographic code'''

import struct

def rc4(message, key, skip=256):
    s = range(256)  #0..255
    k = [ord(x) for x in key]   #unpack 'C*'
    message = [ord(x) for x in message]

    def swap(x, y):
        s[x], s[y] = s[y], s[x]

    x = y = 0
    for x in xrange(256):
        y = (y + s[x] + k[x % len(k)]) % 256
        swap(x, y)

    x = y = 0
    for x in xrange(skip):
        x = (x + 1) % 256
        y = (y + s[x]) % 256
        swap(x, y)

    for i in xrange(len(message)):
        x = (x + 1) % 256
        y = (y + s[x]) % 256
        swap(x, y)
        message[i] = message[i] ^ s[(s[x] + s[y]) % 256]

    return ''.join([chr(x) for x in message])

class RC6(object):
    def __init__(self, key):
        self.state = S = []
        key += "\0" * (4 - len(key) & 3) # pad key

        L = list(struct.unpack("<%sL" % (len(key) / 4), key))

        S.append(0xb7e15163)
        for i in range(43):
            S.append(_add(S[i], 0x9e3779b9))

        v = max(132, len(L) * 3)

        A = B = i = j = 0

        for n in range(v):
            A = S[i] = _rol(_add(S[i], A, B), 3)
            B = L[j] = _rol(_add(L[j] + A + B), _add(A + B))
            i = (i + 1) % len(S)
            j = (j + 1) % len(L)

    def encrypt(self, block):
        S = self.state
        A, B, C, D = struct.unpack("<4L", block.ljust(16, '\0'))

        B = _add(B, S[0])
        D = _add(D, S[1])

        for i in range(1, 21): # 1..20
            t = _rol(_mul(B, _rol(B, 1) | 1), 5)
            u = _rol(_mul(D, _rol(D, 1) | 1), 5)
            A = _add(_rol(A ^ t, u), S[2 * i])
            C = _add(_rol(C ^ u, t), S[2 * i + 1])

            A, B, C, D = B, C, D, A

        A = _add(A, S[42])
        C = _add(C, S[43])

        return struct.pack("<4L", A, B, C, D)

    def decrypt(self, block):
        S = self.state
        A, B, C, D = struct.unpack("<4L", block + "\0" * 16)

        C = _add(C, -S[43])
        A = _add(A, -S[42])

        for i in range(20,0,-1): # 20..1
            A, B, C, D = D, A, B, C

            u = _rol(_mul(D, _add(_rol(D, 1) | 1)), 5)
            t = _rol(_mul(B, _add(_rol(B, 1) | 1)), 5)
            C = _ror(_add(C, -S[2 * i + 1]), t) ^ u
            A = _ror(_add(A, -S[2 * i]), u) ^ t

        D = _add(D, -S[1])
        B = _add(B, -S[0])

        return struct.pack("<4L", A, B, C, D)

# helper functions for rc6

def _add(*args):
    return sum(args) % 4294967296

def _rol(x, n):
    n = 31 & n
    return x << n | 2 ** n - 1 & x >> 32 - n

def _ror(x, y): # rorororor
    return _rol(x, 32 - (31 & y))

def _mul(a, b):
    return (((a >> 16) * (b & 65535) + (b >> 16) * (a & 65535)) * 65536 +
            (a & 65535) * (b & 65535)) % 4294967296 
