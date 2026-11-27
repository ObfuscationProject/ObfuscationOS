/* The ppc probe link has no soft-float libgcc (the toolchain ships only the
 * hard-float multilib), yet musl's printf references its double helpers for
 * floating conversions. A probe that formats only integers defines them here,
 * trapping if one were ever called, so libgcc's hard-float members are not
 * linked. Include it once, before the probe source; it is empty off ppc. */
#ifndef PPC_INTEGER_PRINTF_H
#define PPC_INTEGER_PRINTF_H
#if defined(__powerpc__)
#define PPC_INTEGER_PRINTF_TRAP(name) void name(void); void name(void) { __builtin_trap(); }
PPC_INTEGER_PRINTF_TRAP(__adddf3)
PPC_INTEGER_PRINTF_TRAP(__subdf3)
PPC_INTEGER_PRINTF_TRAP(__muldf3)
PPC_INTEGER_PRINTF_TRAP(__fixdfsi)
PPC_INTEGER_PRINTF_TRAP(__fixunsdfsi)
PPC_INTEGER_PRINTF_TRAP(__floatsidf)
PPC_INTEGER_PRINTF_TRAP(__floatunsidf)
PPC_INTEGER_PRINTF_TRAP(__nedf2)
#undef PPC_INTEGER_PRINTF_TRAP
#endif
#endif
