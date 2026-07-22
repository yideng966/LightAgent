"""
WeCom (企业微信) smart-bot callback message encryption/decryption.

Adapted from the official `WXBizJsonMsgCrypt` sample (JSON variant) used by the
AI bot callback (webhook) mode. The bot's receive-message callback delivers
AES-256-CBC encrypted JSON payloads, and passive replies must be encrypted the
same way before being returned in the HTTP response.

For an enterprise-internal smart bot, ``receive_id`` is always an empty string.
"""

import base64
import hashlib
import random
import socket
import struct
import time

from Crypto.Cipher import AES

from common.log import logger

# Error codes (mirrors the official ierror.py)
WXBizMsgCrypt_OK = 0
WXBizMsgCrypt_ValidateSignature_Error = -40001
WXBizMsgCrypt_ParseJson_Error = -40002
WXBizMsgCrypt_ComputeSignature_Error = -40003
WXBizMsgCrypt_IllegalAesKey = -40004
WXBizMsgCrypt_ValidateCorpid_Error = -40005
WXBizMsgCrypt_EncryptAES_Error = -40006
WXBizMsgCrypt_DecryptAES_Error = -40007
WXBizMsgCrypt_IllegalBuffer = -40008
WXBizMsgCrypt_EncodeBase64_Error = -40009
WXBizMsgCrypt_DecodeBase64_Error = -40010
WXBizMsgCrypt_GenReturnJson_Error = -40011


class FormatException(Exception):
    pass


def _gen_sha1(token, timestamp, nonce, encrypt):
    """Compute the WeCom message signature with SHA1 over the sorted parts."""
    try:
        if isinstance(encrypt, bytes):
            encrypt = encrypt.decode("utf-8")
        sortlist = [str(token), str(timestamp), str(nonce), str(encrypt)]
        sortlist.sort()
        sha = hashlib.sha1()
        sha.update("".join(sortlist).encode("utf-8"))
        return WXBizMsgCrypt_OK, sha.hexdigest()
    except Exception as e:
        logger.error(f"[WecomBot] compute signature error: {e}")
        return WXBizMsgCrypt_ComputeSignature_Error, None


class _PKCS7Encoder:
    """PKCS#7 padding with a 32-byte block size (AES-256)."""

    block_size = 32

    def encode(self, text: bytes) -> bytes:
        text_length = len(text)
        amount_to_pad = self.block_size - (text_length % self.block_size)
        if amount_to_pad == 0:
            amount_to_pad = self.block_size
        pad = bytes([amount_to_pad])
        return text + pad * amount_to_pad

    def decode(self, decrypted: bytes) -> bytes:
        pad = decrypted[-1]
        if pad < 1 or pad > 32:
            pad = 0
        return decrypted[:-pad] if pad else decrypted


class _Prpcrypt:
    """AES-256-CBC encrypt/decrypt for WeCom callback messages."""

    def __init__(self, key: bytes):
        self.key = key
        self.mode = AES.MODE_CBC

    def encrypt(self, text: str, receive_id: str):
        text_bytes = text.encode()
        # 16-byte random prefix + network-order length + body + receive_id
        text_bytes = (
            self._get_random_str()
            + struct.pack("I", socket.htonl(len(text_bytes)))
            + text_bytes
            + receive_id.encode()
        )
        text_bytes = _PKCS7Encoder().encode(text_bytes)
        try:
            cryptor = AES.new(self.key, self.mode, self.key[:16])
            ciphertext = cryptor.encrypt(text_bytes)
            return WXBizMsgCrypt_OK, base64.b64encode(ciphertext)
        except Exception as e:
            logger.error(f"[WecomBot] AES encrypt error: {e}")
            return WXBizMsgCrypt_EncryptAES_Error, None

    def decrypt(self, text, receive_id: str):
        try:
            cryptor = AES.new(self.key, self.mode, self.key[:16])
            plain_text = cryptor.decrypt(base64.b64decode(text))
        except Exception as e:
            logger.error(f"[WecomBot] AES decrypt error: {e}")
            return WXBizMsgCrypt_DecryptAES_Error, None
        try:
            pad = plain_text[-1]
            content = plain_text[16:-pad]
            json_len = socket.ntohl(struct.unpack("I", content[:4])[0])
            json_content = content[4 : json_len + 4].decode("utf-8")
            from_receive_id = content[json_len + 4 :].decode("utf-8")
        except Exception as e:
            logger.error(f"[WecomBot] illegal buffer when decrypting: {e}")
            return WXBizMsgCrypt_IllegalBuffer, None
        if from_receive_id != receive_id:
            logger.error(
                f"[WecomBot] receive_id not match: expect={receive_id}, got={from_receive_id}"
            )
            return WXBizMsgCrypt_ValidateCorpid_Error, None
        return WXBizMsgCrypt_OK, json_content

    @staticmethod
    def _get_random_str() -> bytes:
        return str(random.randint(1000000000000000, 9999999999999999)).encode()


class WecomBotCrypt:
    """High-level helper for verifying URLs and (de)crypting callback messages."""

    def __init__(self, token: str, encoding_aes_key: str, receive_id: str = ""):
        try:
            self.key = base64.b64decode(encoding_aes_key + "=")
            assert len(self.key) == 32
        except Exception:
            raise FormatException("[WecomBot] invalid EncodingAESKey")
        self.token = token
        self.receive_id = receive_id

    def verify_url(self, msg_signature, timestamp, nonce, echostr):
        ret, signature = _gen_sha1(self.token, timestamp, nonce, echostr)
        if ret != 0:
            return ret, None
        if signature != msg_signature:
            return WXBizMsgCrypt_ValidateSignature_Error, None
        pc = _Prpcrypt(self.key)
        return pc.decrypt(echostr, self.receive_id)

    def encrypt_msg(self, reply_msg: str, nonce: str, timestamp: str = None):
        """Encrypt a passive-reply JSON string and return the full response JSON.

        Returns (ret, response_dict). On success ret==0 and response_dict is a
        dict with encrypt/msgsignature/timestamp/nonce fields.
        """
        pc = _Prpcrypt(self.key)
        ret, encrypt = pc.encrypt(reply_msg, self.receive_id)
        if ret != 0:
            return ret, None
        encrypt = encrypt.decode("utf-8")
        if timestamp is None:
            timestamp = str(int(time.time()))
        ret, signature = _gen_sha1(self.token, timestamp, nonce, encrypt)
        if ret != 0:
            return ret, None
        return WXBizMsgCrypt_OK, {
            "encrypt": encrypt,
            "msgsignature": signature,
            "timestamp": timestamp,
            "nonce": nonce,
        }

    def decrypt_msg(self, post_data, msg_signature, timestamp, nonce):
        """Verify signature and decrypt the encrypted callback payload.

        ``post_data`` may be the raw request body (bytes/str) containing
        ``{"encrypt": "..."}`` or the already-extracted encrypt string.
        Returns (ret, plaintext_json_str).
        """
        import json

        encrypt = None
        if isinstance(post_data, (bytes, bytearray)):
            post_data = post_data.decode("utf-8")
        if isinstance(post_data, str):
            try:
                encrypt = json.loads(post_data).get("encrypt")
            except Exception:
                encrypt = post_data
        elif isinstance(post_data, dict):
            encrypt = post_data.get("encrypt")
        if not encrypt:
            return WXBizMsgCrypt_ParseJson_Error, None

        ret, signature = _gen_sha1(self.token, timestamp, nonce, encrypt)
        if ret != 0:
            return ret, None
        if signature != msg_signature:
            logger.error("[WecomBot] callback signature not match")
            return WXBizMsgCrypt_ValidateSignature_Error, None
        pc = _Prpcrypt(self.key)
        return pc.decrypt(encrypt, self.receive_id)
