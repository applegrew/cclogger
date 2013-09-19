#Based on: http://www.turnkeylinux.org/blog/python-symmetric-encryption

import zlib
from Crypto.Cipher import AES
import base64
import hashlib

HASH_LEN = 64 # Characters for SHA-256

class CheckSumError(Exception):
    pass

def _lazysecret(secret, blocksize=32, padding='}'):
    """pads secret if not legal AES block size (16, 24, 32)"""
    if not len(secret) in (16, 24, 32):
        return secret + (blocksize - len(secret)) * padding
    return secret

def getHash(s):
    h = hashlib.new('sha256')
    h.update(s)
    return h.hexdigest()

def encrypt(plaintext, secret, lazy=True, checksum=True, baseEncode=True):
    """encrypt plaintext with secret
    plaintext   - content to encrypt
    secret      - secret to encrypt plaintext
    lazy        - pad secret if less than legal blocksize (default: True)
    checksum    - attach crc32 byte encoded (default: True)
    baseEncode  - base64 encode the output (default: True)
    returns ciphertext
    """

    secret = _lazysecret(secret) if lazy else secret
    iv = "\0" * AES.block_size
    encobj = AES.new(secret, AES.MODE_CFB, iv)

    if checksum:
        plaintext += getHash(plaintext)

    ciphertext = encobj.encrypt(plaintext)

    if baseEncode:
        ciphertext = base64.b64encode(ciphertext)

    return ciphertext

def decrypt(ciphertext, secret, lazy=True, checksum=True, baseEncode=True):
    """decrypt ciphertext with secret
    ciphertext  - encrypted content to decrypt
    secret      - secret to decrypt ciphertext
    lazy        - pad secret if less than legal blocksize (default: True)
    checksum    - verify crc32 byte encoded checksum (default: True)
    baseEncode  - the ciphertext is base64 encoded (default: True)
    returns plaintext
    """

    if baseEncode:
        ciphertext = base64.b64decode(ciphertext)

    secret = _lazysecret(secret) if lazy else secret
    iv = "\0" * AES.block_size
    encobj = AES.new(secret, AES.MODE_CFB, iv)
    plaintext = encobj.decrypt(ciphertext)

    if checksum:
        hash_, plaintext = (plaintext[-HASH_LEN:], plaintext[:-HASH_LEN])
        if not hash_ == getHash(plaintext):
            raise CheckSumError("checksum mismatch")

    return plaintext

