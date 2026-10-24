"""Pure readers for journalled native-login qualification; no execution claims."""
import hashlib
import hmac
import re

SEED = b'OKACCOUNTS 1\nstate unconfigured\n'
CUT = b'NATIVE_LOGIN_CUT state=pending publication=not-attempted staging=persistent'
SESSION = re.compile(rb'^NATIVE_LOGIN_SESSION pid=([1-9][0-9]*) ppid=1 uid=0 gid=0 '
                     rb'epoch=([1-9][0-9]*) user=qual_admin home=/root\r?$', re.M)
ACCOUNT = re.compile(rb'OKACCOUNTS 1\nstate (pending|active)\nname qual_admin\nuid 0\ngid 0\n'
    rb'home /root\nkdf pbkdf2-hmac-sha256\nrounds 600000\nsalt ([0-9a-f]{32})\n'
    rb'verifier ([0-9a-f]{64})\n')


def need(value, message):
    if not value:
        raise ValueError(message)


def account(data, password, state):
    match = ACCOUNT.fullmatch(data)
    need(match and match[1].decode() == state, 'noncanonical or unexpected actual account state')
    salt = bytes.fromhex(match[2].decode())
    verifier = bytes.fromhex(match[3].decode())
    need(hmac.compare_digest(hashlib.pbkdf2_hmac('sha256', password, salt, 600000, 32), verifier),
         'independent verifier differs from the chosen password')
    return dict(state=state, name='qual_admin', uid=0, gid=0, home='/root', rounds=600000,
                salt_hex=salt.hex(), verifier_hex=verifier.hex(), sha256=hashlib.sha256(data).hexdigest())


def serial(data, passwords, sessions, *, cut=False, publications=()):
    for marker in (b'OK_TEST_FAIL', b'NATIVE_LOGIN_FIXTURE_FAIL', b'event=fatal-hold', b'Kernel panic', b'boot=failed'):
        need(marker not in data, 'native login guest failed: ' + marker.decode())
    need(b'OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw journal=ordered-data' in data,
         'actual ordered journalled root execution absent')
    for password in passwords:
        need(len(password) >= 8, 'qualification secret must support echo detection')
        need(not any(password[i:i + 8] in data for i in range(len(password) - 7)), 'password input was echoed')
    found = [(int(pid), int(epoch)) for pid, epoch in SESSION.findall(data)]
    need(len(found) == sessions and all(pid > 1 and 0 < epoch <= 0x3fffffff for pid, epoch in found),
         'actual direct-exec session identity differs')
    need(len({pid for pid, epoch in found}) == len(found) and
         all(found[i][1] < found[i + 1][1] for i in range(len(found) - 1)),
         'session lease generation was reused')
    need(data.count(CUT) == int(cut), 'staging cut marker count differs')
    actual = tuple(re.findall(rb'^NATIVE_LOGIN_PUBLICATION state=(pending|active)\r?$', data, re.M))
    need(actual == tuple(value.encode() for value in publications), 'actual publication order differs')
    return dict(sessions=[dict(pid=pid, epoch=epoch) for pid, epoch in found],
                staging_cut=cut, publications=list(publications), password_echo=False,
                serial_sha256=hashlib.sha256(data).hexdigest())
