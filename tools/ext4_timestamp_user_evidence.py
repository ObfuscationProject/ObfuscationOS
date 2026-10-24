"""Independent raw ext4 oracle for the bounded native/musl maintenance fixture."""
import struct


class Image:
    def __init__(self, data):
        self.data = data
        self.block = 1024 << self.u32(1048)
        self.stride = self.u16(1112)
        if self.u16(1080) != 0xef53 or self.block not in (1024, 2048, 4096) or self.stride != 256:
            raise ValueError('unsupported raw fixture geometry')

    def u16(self, at): return struct.unpack_from('<H', self.data, at)[0]
    def u32(self, at): return struct.unpack_from('<I', self.data, at)[0]

    def inode(self, number):
        if not 0 < number <= self.u32(1024): raise ValueError('inode number')
        group, index = divmod(number - 1, self.u32(1064))
        table = self.u32((self.u32(1044) + 1) * self.block + group * 32 + 8)
        at = table * self.block + index * self.stride
        if at + self.stride > len(self.data): raise ValueError('inode outside disk')
        return at

    def content(self, number):
        at = self.inode(number)
        size = self.u32(at + 4)
        if self.u16(at) & 0xf000 == 0xa000 and size < 60:
            return self.data[at + 40:at + 40 + size]
        if self.u16(at + 40) != 0xf30a or self.u16(at + 46) != 0 or self.u16(at + 42) > 4:
            raise ValueError('fixture requires bounded inline extents')
        output = bytearray(size)
        for index in range(self.u16(at + 42)):
            entry = at + 52 + index * 12
            logical, length = self.u32(entry), self.u16(entry + 4)
            if length >= 32768 or self.u16(entry + 6): raise ValueError('unsupported fixture extent')
            physical = self.u32(entry + 8)
            count = min(length * self.block, max(0, size - logical * self.block))
            if (physical + length) * self.block > len(self.data): raise ValueError('extent outside disk')
            output[logical * self.block:logical * self.block + count] = self.data[physical * self.block:physical * self.block + count]
        return bytes(output)

    def children(self, number):
        if self.u16(self.inode(number)) & 0xf000 != 0x4000: raise ValueError('not directory')
        data = self.content(number)
        result = {}
        for start in range(0, len(data), self.block):
            offset = start
            while offset < start + self.block:
                ino, length, name_length = struct.unpack_from('<IHB', data, offset)
                if length < 8 or length % 4 or offset + length > start + self.block or name_length > length - 8:
                    raise ValueError('malformed raw directory')
                if ino:
                    name = data[offset + 8:offset + 8 + name_length].decode('ascii')
                    if name in result: raise ValueError('duplicate raw name')
                    result[name] = ino
                offset += length
        return result

    def lookup(self, path):
        number = 2
        for name in path.strip('/').split('/'):
            if name: number = self.children(number)[name]
        return number

    def fields(self, number):
        at = self.inode(number)
        extra = self.u16(at + 128)
        if extra > 128 or extra % 4: raise ValueError('invalid raw timestamp extent')
        result = []
        for base, extension in ((8, 140), (16, 136), (12, 132)):
            seconds = struct.unpack_from('<i', self.data, at + base)[0]
            word = self.u32(at + extension) if extension + 4 <= 128 + extra else 0
            if word >> 2 >= 1000000000: raise ValueError('raw nanosecond overflow')
            result.append((seconds + (word & 3) * 4294967296, word >> 2))
        return result


def validate(text, initial_bytes, final_bytes):
    required = ('EXT4_TIME_NATIVE_PASS authority=uid1000 clock-set=EPERM automatic-times=enabled',
                'EXT4_TIME_MUSL_PASS authority=uid1000 clock-set=EPERM linux-stat=qualified',
                'EXT4_TIME_USER_CREDENTIALS uid=1000 euid=1000 gid=1000 egid=1000 before-entry=1',
                'EXT4_TIME_USER_STORAGE virtio=1 maintained=1 baseline=retained-fixture clock=administrator-software',
                'EXT4_TIME_USER_FIXTURE_PASS exit=0 actual-native-and-musl=1 uid=1000 linux-stat=qualified')
    if any(text.splitlines().count(line) != 1 for line in required) or '_FAIL' in text:
        raise ValueError('missing or failed user fixture marker')
    expected = {
        'native': [('create','native-time',7),('write','native-time',6),('same-truncate','native-time',6),
                   ('link','native-time',4),('rename','native-renamed',4),('unlink-alias','native-renamed',4),
                   ('pread','native-renamed',1),('symlink','native-link',7),('readlink','native-link',1),('mkdir','native-dir',7)],
        'musl': [('create','musl-time',7),('write','musl-time',6),('pwrite','musl-time',6),('pread','musl-time',1),
                 ('read-eof','musl-time',1),('create','musl-truncate',7),('open-truncate','musl-truncate',6),
                 ('mkdir','musl-dir',7),('getdents','musl-dir',1),('getdents-eof','musl-dir',1),('readlink','fixture-link',1)]}
    events, sequence, last_time = {}, {'native': [], 'musl': []}, None
    for line in text.splitlines():
        if not line.startswith('EXT4_TIME_USER_EVENT '): continue
        tokens = [word.split('=', 1) for word in line.split()[1:]]
        record = dict(tokens)
        if len(record) != len(tokens) or set(record) != {'api','event','path','mask','before_s','before_n','after_s','after_n'}:
            raise ValueError('invalid event fields')
        api, event, path = record['api'], record['event'], record['path']
        if api not in sequence or not path.startswith('/home/'): raise ValueError('unknown event origin')
        key = (api, event, path)
        if key in events: raise ValueError('duplicate event')
        for field in ('mask','before_s','before_n','after_s','after_n'): record[field] = int(record[field])
        low, high = (record['before_s'],record['before_n']), (record['after_s'],record['after_n'])
        if not 2208988800 <= low[0] <= high[0] <= 2208989100 or not 0 <= low[1] < 1000000000 or not 0 <= high[1] < 1000000000 or low > high or (last_time and low < last_time):
            raise ValueError('clock bracket order/range')
        last_time = high
        sequence[api].append((event,path[len('/home/'):],record['mask']))
        events[key] = record
    if sequence != expected: raise ValueError('incomplete user event sequence')
    before, after = Image(initial_bytes), Image(final_bytes)
    if before.block != after.block or before.stride != after.stride: raise ValueError('geometry changed')
    original_link = before.lookup('/home/fixture-link')
    targets = {
        'native-renamed': ('native', ('pread','same-truncate','unlink-alias'), 'native-time'),
        'native-link': ('native', ('readlink','symlink','symlink'), 'native-link'),
        'native-dir': ('native', ('mkdir','mkdir','mkdir'), 'native-dir'),
        'musl-time': ('musl', ('read-eof','pwrite','pwrite'), 'musl-time'),
        'musl-truncate': ('musl', ('create','open-truncate','open-truncate'), 'musl-truncate'),
        'musl-dir': ('musl', ('getdents-eof','mkdir','mkdir'), 'musl-dir'),
        'fixture-link': ('musl', ('readlink',None,None), 'fixture-link')}
    output = {}
    event_samples = {}
    initial_names = before.children(before.lookup('/home'))
    for name, (api, labels, old_name) in targets.items():
        number = after.lookup('/home/' + name)
        at = after.inode(number)
        values = after.fields(number)
        if name == 'fixture-link':
            if number != original_link: raise ValueError('baseline symlink identity changed')
        else:
            if name in initial_names or old_name in initial_names or after.u16(at + 128) != 16:
                raise ValueError('new inode baseline or extra-size mismatch')
            if (after.u16(at + 2) | after.u16(at + 120) << 16) != 1000 or (after.u16(at + 24) | after.u16(at + 122) << 16) != 1000:
                raise ValueError('new inode owner mismatch')
        for index, label in enumerate(labels):
            if label is None:
                if values[index] != before.fields(original_link)[index]: raise ValueError('untouched baseline field changed')
                continue
            path = '/home/' + (old_name if name == 'native-renamed' and label == 'same-truncate' else name)
            key = (api, label, path)
            event = events[key]
            if not event['mask'] & (1 << index): raise ValueError('field not selected by event')
            if not (event['before_s'], event['before_n']) <= values[index] <= (event['after_s'], event['after_n']):
                raise ValueError('stored field outside event bracket: '+name+'/'+str(index))
            if key in event_samples and values[index] != event_samples[key]:
                raise ValueError('different stored samples for one event: '+name+'/'+label)
            event_samples[key] = values[index]
        output[name] = {'inode':number,'times':values,'extra_isize':after.u16(at + 128)}
    if after.content(after.lookup('/home/native-renamed')) != b'native' or after.content(after.lookup('/home/musl-time')) != b'abZdef' or after.content(after.lookup('/home/musl-truncate')):
        raise ValueError('final data mismatch')
    if after.content(after.lookup('/home/native-link')) != b'native-renamed' or after.content(original_link) != b'musl-time':
        raise ValueError('final symlink mismatch')
    names = after.children(after.lookup('/home'))
    if 'native-time' in names or 'native-alias' in names: raise ValueError('removed name survived')
    return {'event_count':len(events),'raw_nodes':output,'uid':1000,'new_extra_isize':16,
            'clock_source':'administrator-software','linux_stat':'qualified','user_mode':True}
