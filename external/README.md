# External dependencies

`ObfuscationKernel` is expected at `external/ObfuscationKernel` and should be
kept at the `v0.1.0-2` baseline commit
`b8a4d5af31141663686587b97409c53f29114f2e`.

Initialize it with:

```sh
git submodule update --init --recursive external/ObfuscationKernel
```

The userland build can fall back to the local `uapi/include` headers while the
submodule is unavailable, but `xmake build kernel-submodule-check` requires the
real checkout.
