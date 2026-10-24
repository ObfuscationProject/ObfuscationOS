"""Read retained native-login compile, dependency, object and link originals."""
from pathlib import Path
import hashlib
import re
import shlex
from native_login_evidence import need


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


class LiteralTable:
    """Parse xmake's literal dependency records without evaluating Lua code."""
    def __init__(self, text):
        self.text, self.pos = text, 0

    def ws(self):
        while self.pos < len(self.text) and self.text[self.pos].isspace():
            self.pos += 1

    def take(self, token):
        self.ws()
        need(self.text.startswith(token, self.pos), 'dependency literal syntax requires ' + repr(token))
        self.pos += len(token)

    def string(self):
        self.take('"')
        output = ''
        while self.pos < len(self.text):
            char = self.text[self.pos]
            self.pos += 1
            if char == '"':
                return output
            if char == '\\':
                need(self.pos < len(self.text), 'truncated literal escape')
                char = self.text[self.pos]
                self.pos += 1
                escapes = {'\\': '\\', '"': '"', 'n': '\n', 'r': '\r', 't': '\t', '\n': '\n'}
                need(char in escapes, 'unsupported literal escape')
                char = escapes[char]
            else:
                need(char not in '\r\n', 'raw newline in string literal')
            output += char
        raise ValueError('unterminated string literal')

    def value(self):
        self.ws()
        need(self.pos < len(self.text), 'missing literal')
        if self.text[self.pos] == '"':
            return self.string()
        self.take('{')
        items, fields, kind = [], {}, None
        while True:
            self.ws()
            if self.text.startswith('}', self.pos):
                self.pos += 1
                return fields if kind == 'map' else items
            key = re.match(r'[A-Za-z_][A-Za-z_0-9]*', self.text[self.pos:])
            if key:
                need(kind in (None, 'map'), 'mixed literal table')
                kind, name = 'map', key.group()
                self.pos += len(name)
                self.take('=')
                need(name not in fields, 'duplicate literal field')
                fields[name] = self.value()
            else:
                need(kind in (None, 'list'), 'mixed literal table')
                kind = 'list'
                items.append(self.value())
            self.ws()
            if self.text.startswith(',', self.pos):
                self.pos += 1
            else:
                need(self.text.startswith('}', self.pos), 'literal separator missing')

    def parse(self):
        result = self.value()
        self.ws()
        need(self.pos == len(self.text), 'trailing nonliteral content')
        return result


def commands(text):
    rows = []
    for line in re.sub(r'\x1b\[[0-9;]*m', '', text).splitlines():
        try:
            argv = shlex.split(line)
        except ValueError:
            continue
        if argv and argv[0].endswith(('-gcc', '-g++', '-ar', '-objcopy')):
            rows.append(argv)
    return rows


def original_products(consumer):
    """Inventory originals, with no rebuild or success assertion."""
    products = {}
    for tree, suffix in (('build/.objs', '.o'), ('build/.deps', '.o.d')):
        for path in sorted((consumer / tree).rglob('*' + suffix)):
            need(path.is_file() and not path.is_symlink(), 'regular original build product required')
            products[path.relative_to(consumer).as_posix()] = sha(path)
    return products


def elf(path, kind):
    raw = path.read_bytes()
    need(len(raw) >= 64 and raw[:8] == b'\x7fELF\x02\x01\x01\x00' and
         int.from_bytes(raw[16:18], 'little') == kind and int.from_bytes(raw[18:20], 'little') == 62,
         'native x86_64 ELF identity differs: ' + str(path))
    return sha(path)


def archive_members(path):
    raw, at, strings, members = path.read_bytes(), 8, b'', {}
    need(raw.startswith(b'!<arch>\n'), 'CRT archive magic differs')
    while at < len(raw):
        need(at + 60 <= len(raw), 'archive header bounds')
        header = raw[at:at + 60]
        need(header[58:60] == b'`\n', 'archive header trailer')
        size = int(header[48:58].decode('ascii').strip())
        name = header[:16].decode('ascii').strip()
        at += 60
        need(size >= 0 and at + size <= len(raw), 'archive member bounds')
        body = raw[at:at + size]
        at += size + (size & 1)
        if name == '//':
            strings = body
            continue
        if name in ('/', '/SYM64/'):
            continue
        if name.startswith('/'):
            start = int(name[1:])
            end = strings.find(b'/\n', start)
            need(start >= 0 and end >= start, 'archive long-name bounds')
            name = strings[start:end].decode('ascii')
        else:
            name = name.rstrip('/')
        need(name and name not in members, 'duplicate archive member')
        members[name] = body
    need(at == len(raw), 'archive tail bounds')
    return members


def inspect(consumer, sdk, mode, manifest, sources, products, tools, log):
    rows = commands(log)
    need(rows, 'actual verbose build commands absent')
    objects, links, used_products, units = {}, {}, set(), set()
    toolchain = None
    for argv in rows:
        tool = Path(argv[0])
        need(tool.is_absolute() and str(tool.resolve()) in tools and sha(tool) == tools[str(tool.resolve())],
             'unbound actual build tool: ' + str(tool))
        if tool.name.endswith(('-gcc', '-g++')):
            if toolchain is None:
                toolchain = tool.parent.parent.resolve()
            need(tool.parent.parent.resolve() == toolchain, 'mixed native compiler toolchains')
        if '-c' not in argv:
            if '-o' in argv and argv[0].endswith(('-gcc', '-g++')):
                output = argv[argv.index('-o') + 1]
                need(output not in links, 'duplicate actual link output')
                links[output] = argv
            continue
        need('-o' in argv and '-ffreestanding' in argv, 'native compile contract absent')
        source = Path(argv[-1])
        source = source.resolve() if source.is_absolute() else (consumer / source).resolve()
        need(source.is_relative_to(consumer), 'foreign compiled source')
        relative = source.relative_to(consumer).as_posix()
        need(relative in sources and sha(source) == sources[relative], 'unfrozen actual compiled source')
        if relative.endswith('.c'):
            need(all(flag in argv for flag in ('-std=c11', '-fno-builtin', '-fno-stack-protector', '-Wall', '-Wextra')),
                 'native C compile options differ')
            need(all(flag in argv for flag in (('-g', '-O0') if mode == 'debug' else ('-O3',))),
                 'native C build mode differs')
        elif relative.endswith('.cpp'):
            need('-std=c++23' in argv and all(flag in argv for flag in manifest['cxxflags']) and
                 all('-D' + value in argv for value in manifest['defines']), 'native C++23 SDK compile options differ')
        name = argv[argv.index('-o') + 1]
        need(name.startswith('build/.objs/') and name not in objects, 'actual object path differs or duplicates')
        dependency_name = name.replace('build/.objs/', 'build/.deps/', 1) + '.d'
        for item in (name, dependency_name):
            need(item in products and sha(consumer / item) == products[item], 'retained original build product differs')
            used_products.add(item)
        elf(consumer / name, 1)
        dependency = LiteralTable((consumer / dependency_name).read_text()).parse()
        need(set(dependency) == {'files', 'depfiles', 'depfiles_format', 'values'} and
             dependency['files'] == [relative] and dependency['depfiles_format'] == 'gcc', 'original dependency schema/source differs')
        normalize = lambda values: [value.replace('\\"', '"') for value in values]
        need(dependency['values'][0] == argv[0] and
             normalize(dependency['values'][1]) == normalize(argv[2:argv.index('-o')]), 'original compiler/dependency options differ')
        target, names = dependency['depfiles'].replace('\\\n', ' ').split(':', 1)
        need(target.strip() == name, 'original dependency object target differs')
        dependencies = {}
        for token in shlex.split(names):
            path = Path(token)
            path = path.resolve() if path.is_absolute() else (consumer / path).resolve()
            need(path.is_relative_to(consumer) or path.is_relative_to(sdk) or path.is_relative_to(toolchain),
                 'foreign header fallback: ' + str(path))
            digest = sha(path)
            if path.is_relative_to(consumer):
                key = path.relative_to(consumer).as_posix()
                need(sources.get(key) == digest or key == 'build/x86_64/' + mode + '/boot.okar.inc', 'unfrozen compile dependency')
            elif path.is_relative_to(sdk):
                need(manifest['files'].get(path.relative_to(sdk).as_posix()) == digest, 'unmanifested SDK compile dependency')
            dependencies[str(path)] = digest
        need(str(source) in dependencies, 'actual source missing from dependency original')
        units.add(relative)
        objects[name] = dict(source=relative, sha256=products[name], dependency_sha256=products[dependency_name], dependencies=dependencies)
    need(set(products) == used_products, 'unlogged original object or dependency product')
    build = consumer / 'build/x86_64' / mode
    crt_objects = {name: value for name, value in objects.items() if name.startswith('build/.objs/okcrt/')}
    crt = build / 'lib/libokcrt.a'
    members = archive_members(crt)
    need(len({Path(name).name for name in crt_objects}) == len(crt_objects) and
         set(members) == {Path(name).name for name in crt_objects} and crt_objects,
         'CRT archive original object inventory differs')
    for name in crt_objects:
        need(members[Path(name).name] == (consumer / name).read_bytes(), 'CRT archive member differs from actual compiled object')
    ar = [argv for argv in rows if argv[0].endswith('-ar') and str(crt) in argv]
    need(len(ar) == 1 and ar[0][1:3] == ['-cr', str(crt)] and len(ar[0][3:]) == len(crt_objects) and
         set(ar[0][3:]) == set(crt_objects), 'actual CRT archive command/object association differs')
    login_sources = {name for name in sources if name.startswith('apps/login/') and name.endswith('.c')}
    for target, output, expected, wrapped in (
            ('app-login', build / 'apps/login.elf', login_sources | {'lib/okcrt/arch/x86_64/crt0.S'}, False),
            ('native-login-cut', build / 'fixtures/native-login-cut.elf', login_sources |
             {'lib/okcrt/arch/x86_64/crt0.S', 'tests/native/native_login_cut.c'}, True),
            ('native-login-session', build / 'fixtures/native-login-session.elf',
             {'lib/okcrt/arch/x86_64/crt0.S', 'tests/native/native_login_session.c'}, False)):
        matches = {name: value for name, value in objects.items() if name.startswith('build/.objs/' + target + '/')}
        need({value['source'] for value in matches.values()} == expected and len(matches) == len(expected),
             'actual login target compilation inventory differs: ' + target)
        argv = links.get(str(output))
        need(argv and set(item for item in argv if item.endswith('.o')) == set(matches) and
             len([item for item in argv if item.endswith('.o')]) == len(matches), 'original login link/object association differs')
        need([item for item in argv if '--wrap' in item] == (['-Wl,--wrap=renameat'] if wrapped else []),
             'production/wrapped login linkage scope differs')
        need('-lokcrt' in argv and '-L' + str(build / 'lib') in argv and
             '-Wl,-T,' + str(consumer / 'lib/okcrt/user.ld') in argv, 'actual native CRT/script link differs')
        elf(output, 2)
    distro = links.get(str(build / 'distro/kernel.elf'))
    need(distro and str(sdk / 'lib/libokernel.a') in distro and str(sdk / 'lib/libokernel_boot.a') in distro and
         '-Wl,-T,' + str(sdk / 'boot/linker.ld') in distro, 'actual exported SDK distro link absent')
    need({'lib/okcrt/src/console.c', 'lib/okcrt/src/storage.c', 'apps/init/native_supervisor.c',
          'apps/init/native_control.c', 'apps/oksh/main.c'} <= units, 'actual production service/console/storage compile units absent')
    return dict(objects=objects, actual_links=links, compiled_units=sorted(units), crt_archive_sha256=sha(crt),
                crt_archive_command=ar[0],
                unwrapped_production_login=True, staged_cohort_rename_wrapper=True)
