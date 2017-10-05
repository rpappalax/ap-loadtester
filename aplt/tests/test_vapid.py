import base64
import hashlib
import os
import json
import unittest
from nose.tools import eq_, ok_
from mock import patch

from jose import jws
from aplt.vapid import Vapid, VapidException

# It's handy if this is readable, but the string shouldn't have
# line breaks in it.
T_PRIVATE = """
MHcCAQEEIPeN1iAipHbt8+/KZ2NIF8NeN24jqAmnMLFZEMocY8RboAoGCCqGSM49
AwEHoUQDQgAEEJwJZq/GN8jJbo1GGpyU70hmP2hbWAUpQFKDByKB81yldJ9GTklB
M5xqEwuPM7VuQcyiLDhvovthPIXx+gsQRQ==
""".replace("\n", "").replace("\r", "")

# PEMs have line breaks at 64 character
T_PRIVATE_PEM = """-----BEGIN EC PRIVATE KEY-----
%s
-----END EC PRIVATE KEY-----
""" % "\n".join([T_PRIVATE[s:s+64] for s in range(0, len(T_PRIVATE), 64)])


T_PUBLIC = """-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEEJwJZq/GN8jJbo1GGpyU70hmP2hb
WAUpQFKDByKB81yldJ9GTklBM5xqEwuPM7VuQcyiLDhvovthPIXx+gsQRQ==
-----END PUBLIC KEY-----
"""

T_PUBLIC_RAW = """EJwJZq_GN8jJbo1GGpyU70hmP2hbWAUpQFKDBy\
KB81yldJ9GTklBM5xqEwuPM7VuQcyiLDhvovthPIXx-gsQRQ=="""


def setup_module(self):
    ff = open('/tmp/private', 'w')
    ff.write(T_PRIVATE_PEM)
    ff.close()
    ff = open('/tmp/public', 'w')
    ff.write(T_PUBLIC)
    ff.close()


def teardown_module(self):
    os.unlink('/tmp/private')
    os.unlink('/tmp/public')


class VapidTestCase(unittest.TestCase):
    def test_init(self):
        v1 = Vapid(private_key_file="/tmp/private")
        eq_(v1.private_key.to_pem(), T_PRIVATE_PEM)
        eq_(v1.public_key.to_pem(), T_PUBLIC)
        v2 = Vapid(private_key=T_PRIVATE)
        eq_(v2.private_key.to_pem(), T_PRIVATE_PEM)
        eq_(v2.public_key.to_pem(), T_PUBLIC)

    @patch("ecdsa.SigningKey.from_pem", side_effect=Exception)
    def test_init_bad_priv(self, mm):
        self.assertRaises(Exception,
                          Vapid,
                          private_key_file="/tmp/private")

    def test_private(self):
        v = Vapid()

        def getKey(v):
            v.private_key

        self.assertRaises(VapidException, getKey, v)

    def test_public(self):
        v = Vapid()

        def getKey(v):
            v.public_key

        self.assertRaises(VapidException, getKey, v)

    def test_gen_key(self):
        v = Vapid()
        v.generate_keys()
        ok_(v.public_key)
        ok_(v.private_key)

    def test_save_private_key(self):
        v = Vapid()
        v.save_private_key("/tmp/p2")
        os.unlink("/tmp/p2")

    def test_save_public_key(self):
        v = Vapid()
        v.generate_keys()
        v.save_public_key("/tmp/p2")
        os.unlink("/tmp/p2")

    def test_validate(self):
        v = Vapid("/tmp/private")
        token = "foobar"
        sig = v.validate(token)
        ok_(v.public_key.verify(
            base64.urlsafe_b64decode(sig + '===='[len(sig) % 4:]),
            token,
            hashfunc=hashlib.sha256))
        eq_(v.verify_token(sig, token), True)

    def test_sign(self):
        v = Vapid(private_key=T_PRIVATE)
        claims = {"aud": "example.com", "sub": "admin@example.com"}
        result = v.sign(claims, "id=previous")
        eq_(result['Crypto-Key'],
            'id=previous,'
            'p256ecdsa=' + T_PUBLIC_RAW.strip('='))
        items = jws.verify(result['Authorization'][7:],
                           v.public_key,
                           algorithms=["ES256"])
        eq_(json.loads(items), claims)
        result = v.sign(claims)
        eq_(result['Crypto-Key'],
            'p256ecdsa=' + T_PUBLIC_RAW.strip('='))

    def test_bad_sign(self):
        v = Vapid(private_key=T_PRIVATE)
        self.assertRaises(VapidException,
                          v.sign,
                          {'sub': "a@e.c"})
        self.assertRaises(VapidException,
                          v.sign,
                          {'aud': "https://e.c"})
