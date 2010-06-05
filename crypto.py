'''Module with misleading name for cryptographic code'''

import struct

def rc4(message, key, skip=256):
    s = range(256)  #0..255
    k = [ord(x) for x in key]   #unpack 'C*'
    message = [ord(x) for x in message]

    def swap(x, y):
        temp = s[x]
        s[x] = s[y]
        s[y] = temp

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

