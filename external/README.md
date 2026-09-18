# External dependencies

The kernel is no longer a submodule or source dependency here. Build
ObfuscationKernel independently and consume its exported SDK from
`../ObfuscationKernel/build/sdk/<arch>/<mode>`, or configure
`--kernel_sdk=/absolute/path/to/sdk`.

See the repository README for the artifact manifest, build and validation
commands. Do not restore a kernel checkout under this directory.
