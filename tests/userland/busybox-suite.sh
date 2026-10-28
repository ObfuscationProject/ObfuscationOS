# Run BusyBox's own testsuite/runtest in the guest (decision 0004). The suite
# expects <bindir>/busybox and <bindir>/.config next to testsuite/; the full
# rootfs profile stages them under /usr/share/busybox. Arguments select applets.
# The script is started through sh: the kernel does not run #! scripts yet.
cd /usr/share/busybox/testsuite || exit 1
exec sh ./runtest "$@"
