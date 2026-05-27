# External dependencies

`ObfuscationKernel` is expected at `external/ObfuscationKernel` and should be
kept at the `v0.1.0` baseline commit
`104f2091feeed4a6f600ea371c44779de5b9bb85`.

Initialize it with:

```sh
git submodule update --init --recursive external/ObfuscationKernel
```

The userland build can fall back to the local `uapi/include` headers while the
submodule is unavailable, but `xmake build kernel-submodule-check` requires the
real checkout.
