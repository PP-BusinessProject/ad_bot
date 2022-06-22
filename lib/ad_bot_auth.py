import asyncio
from dataclasses import dataclass
from hashlib import sha1
from io import BytesIO
from os import urandom
from time import monotonic, time
from typing import Final

from pyrogram import raw
from pyrogram.connection.connection import Connection
from pyrogram.crypto import aes, prime, rsa
from pyrogram.errors import SecurityCheckMismatch
from pyrogram.raw.core import TLObject
from pyrogram.session.auth import Auth, log
from typing_extensions import Self


@dataclass(init=False, frozen=True)
class AdBotAuth(Auth):
    connection: Final[Connection]

    def __init__(self: Self, /, connection: Connection) -> None:
        object.__setattr__(self, 'connection', connection)

    async def create(self: Self, /) -> bytes:
        """
        https://core.telegram.org/mtproto/auth_key
        https://core.telegram.org/mtproto/samples-auth_key
        """
        retries_left = self.MAX_RETRIES

        # The server may close the connection at any time, causing the auth key creation to fail.
        # If that happens, just try again up to MAX_RETRIES times.
        while True:
            try:
                log.info(
                    'Start creating a new auth key on DC%s',
                    self.connection.dc_id,
                )

                # Step 1; Step 2
                nonce = int.from_bytes(urandom(16), 'little', signed=True)
                log.debug('Send req_pq: %s', nonce)
                res_pq = await self.invoke(
                    raw.functions.ReqPqMulti(nonce=nonce)
                )
                log.debug('Got ResPq: %s', res_pq.server_nonce)
                log.debug(
                    'Server public key fingerprints: %s',
                    res_pq.server_public_key_fingerprints,
                )

                for i in res_pq.server_public_key_fingerprints:
                    if i in rsa.server_public_keys:
                        log.debug(f'Using fingerprint: {i}')
                        public_key_fingerprint = i
                        break
                    else:
                        log.debug(f'Fingerprint unknown: {i}')
                else:
                    raise Exception('Public key not found')

                # Step 3
                pq = int.from_bytes(res_pq.pq, 'big')
                log.debug(f'Start PQ factorization: {pq}')
                start = monotonic()
                g = prime.decompose(pq)
                p, q = sorted((g, pq // g))  # p < q
                log.debug(
                    'Done PQ factorization (%ss): %s %s',
                    round(monotonic() - start, 3),
                    p,
                    q,
                )

                # Step 4
                server_nonce = res_pq.server_nonce
                new_nonce = int.from_bytes(urandom(32), 'little', signed=True)

                data = raw.types.PQInnerData(
                    pq=res_pq.pq,
                    p=p.to_bytes(4, 'big'),
                    q=q.to_bytes(4, 'big'),
                    nonce=nonce,
                    server_nonce=server_nonce,
                    new_nonce=new_nonce,
                ).write()

                sha = sha1(data).digest()
                padding = urandom(-(len(data) + len(sha)) % 255)
                data_with_hash = sha + data + padding
                encrypted_data = rsa.encrypt(
                    data_with_hash, public_key_fingerprint
                )

                log.debug('Done encrypt data with RSA')

                # Step 5. TODO: Handle 'server_DH_params_fail'.
                # Code assumes response is ok
                log.debug('Send req_DH_params')
                server_dh_params = await self.invoke(
                    raw.functions.ReqDHParams(
                        nonce=nonce,
                        server_nonce=server_nonce,
                        p=p.to_bytes(4, 'big'),
                        q=q.to_bytes(4, 'big'),
                        public_key_fingerprint=public_key_fingerprint,
                        encrypted_data=encrypted_data,
                    )
                )

                encrypted_answer = server_dh_params.encrypted_answer

                server_nonce = server_nonce.to_bytes(16, 'little', signed=True)
                new_nonce = new_nonce.to_bytes(32, 'little', signed=True)

                tmp_aes_key = (
                    sha1(new_nonce + server_nonce).digest()
                    + sha1(server_nonce + new_nonce).digest()[:12]
                )

                tmp_aes_iv = (
                    sha1(server_nonce + new_nonce).digest()[12:]
                    + sha1(new_nonce + new_nonce).digest()
                    + new_nonce[:4]
                )

                server_nonce = int.from_bytes(
                    server_nonce, 'little', signed=True
                )

                answer_with_hash = aes.ige256_decrypt(
                    encrypted_answer, tmp_aes_key, tmp_aes_iv
                )
                answer = answer_with_hash[20:]

                server_dh_inner_data = TLObject.read(BytesIO(answer))

                log.debug('Done decrypting answer')

                dh_prime = int.from_bytes(server_dh_inner_data.dh_prime, 'big')
                delta_time = server_dh_inner_data.server_time - time()

                log.debug(f'Delta time: {round(delta_time, 3)}')

                # Step 6
                g = server_dh_inner_data.g
                b = int.from_bytes(urandom(256), 'big')
                g_b = pow(g, b, dh_prime).to_bytes(256, 'big')

                retry_id = 0

                data = raw.types.ClientDHInnerData(
                    nonce=nonce,
                    server_nonce=server_nonce,
                    retry_id=retry_id,
                    g_b=g_b,
                ).write()

                sha = sha1(data).digest()
                padding = urandom(-(len(data) + len(sha)) % 16)
                data_with_hash = sha + data + padding
                encrypted_data = aes.ige256_encrypt(
                    data_with_hash, tmp_aes_key, tmp_aes_iv
                )

                log.debug('Send set_client_DH_params')
                set_client_dh_params_answer = await self.invoke(
                    raw.functions.SetClientDHParams(
                        nonce=nonce,
                        server_nonce=server_nonce,
                        encrypted_data=encrypted_data,
                    )
                )

                # TODO: Handle 'auth_key_aux_hash' if the previous step fails

                # Step 7; Step 8
                g_a = int.from_bytes(server_dh_inner_data.g_a, 'big')
                auth_key = pow(g_a, b, dh_prime).to_bytes(256, 'big')
                server_nonce = server_nonce.to_bytes(16, 'little', signed=True)

                # TODO: Handle errors

                #######################
                # Security checks
                #######################

                SecurityCheckMismatch.check(dh_prime == prime.CURRENT_DH_PRIME)
                log.debug('DH parameters check: OK')

                # https://core.telegram.org/mtproto/security_guidelines#g-a-and-g-b-validation
                g_b = int.from_bytes(g_b, 'big')
                SecurityCheckMismatch.check(1 < g < dh_prime - 1)
                SecurityCheckMismatch.check(1 < g_a < dh_prime - 1)
                SecurityCheckMismatch.check(1 < g_b < dh_prime - 1)
                SecurityCheckMismatch.check(
                    2 ** (2048 - 64) < g_a < dh_prime - 2 ** (2048 - 64)
                )
                SecurityCheckMismatch.check(
                    2 ** (2048 - 64) < g_b < dh_prime - 2 ** (2048 - 64)
                )
                log.debug('g_a and g_b validation: OK')

                # https://core.telegram.org/mtproto/security_guidelines#checking-sha1-hash-values
                answer = (
                    server_dh_inner_data.write()
                )  # Call .write() to remove padding
                SecurityCheckMismatch.check(
                    answer_with_hash[:20] == sha1(answer).digest()
                )
                log.debug('SHA1 hash values check: OK')

                # https://core.telegram.org/mtproto/security_guidelines#checking-nonce-server-nonce-and-new-nonce-fields
                # 1st message
                SecurityCheckMismatch.check(nonce == res_pq.nonce)
                # 2nd message
                server_nonce = int.from_bytes(
                    server_nonce, 'little', signed=True
                )
                SecurityCheckMismatch.check(nonce == server_dh_params.nonce)
                SecurityCheckMismatch.check(
                    server_nonce == server_dh_params.server_nonce
                )
                # 3rd message
                SecurityCheckMismatch.check(
                    nonce == set_client_dh_params_answer.nonce
                )
                SecurityCheckMismatch.check(
                    server_nonce == set_client_dh_params_answer.server_nonce
                )
                server_nonce = server_nonce.to_bytes(16, 'little', signed=True)
                log.debug('Nonce fields check: OK')

                # Step 9
                server_salt = aes.xor(new_nonce[:8], server_nonce[:8])

                log.debug(
                    'Server salt: %s',
                    int.from_bytes(server_salt, 'little'),
                )

                log.info(
                    'Done auth key exchange: %s',
                    set_client_dh_params_answer.__class__.__name__,
                )
            except Exception as e:
                if retries_left:
                    retries_left -= 1
                else:
                    raise e

                await asyncio.sleep(1)
                continue
            else:
                return auth_key