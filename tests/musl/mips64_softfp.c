/* Binary128 bit-pattern and libc integration checks for the qualified MIPS N64 ABI. */
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>

#if !defined(__mips64) || __LDBL_MANT_DIG__ != 113 || __BYTE_ORDER__ != __ORDER_BIG_ENDIAN__
#error This fixture requires MIPS64 N64 big-endian binary128 long double.
#endif

typedef long double quad;
typedef int comparison __attribute__((mode(__libgcc_cmp_return__)));
typedef __int128 wide;
typedef unsigned __int128 uwide;
#define BIN(name) extern quad name(quad, quad)
BIN(__addtf3); BIN(__subtf3); BIN(__multf3); BIN(__divtf3);
extern quad __negtf2(quad);
#define CMP(name) extern comparison name(quad, quad)
CMP(__eqtf2); CMP(__netf2); CMP(__letf2); CMP(__lttf2);
CMP(__getf2); CMP(__gttf2); CMP(__unordtf2);
extern quad __extendsftf2(float);
extern quad __extenddftf2(double);
extern float __trunctfsf2(quad);
extern double __trunctfdf2(quad);
extern quad __floatsitf(int); extern quad __floatunsitf(unsigned);
extern quad __floatditf(long); extern quad __floatunditf(unsigned long);
extern quad __floattitf(wide); extern quad __floatuntitf(uwide);
extern int __fixtfsi(quad); extern unsigned __fixunstfsi(quad);
extern long __fixtfdi(quad); extern unsigned long __fixunstfdi(quad);
extern wide __fixtfti(quad); extern uwide __fixunstfti(quad);

static unsigned checks;
static void check(int value, unsigned line)
{
    ++checks;
    if (!value) {
        char text[100];
        int count = snprintf(text, sizeof text, "SOFTFP_FAIL line=%u check=%u\n", line, checks);
        if (count > 0) write(1, text, (size_t)count);
        _Exit(90);
    }
}
#define CHECK(x) check(!!(x), __LINE__)
static quad bits(uint64_t high, uint64_t low)
{
    union { quad value; uint64_t words[2]; } result = {.words = {high, low}};
    return result.value;
}
static void same(quad value, uint64_t high, uint64_t low)
{
    union { quad value; uint64_t words[2]; } result = {.value = value};
    CHECK(result.words[0] == high);
    CHECK(result.words[1] == low);
}
static void mode(unsigned value) { __builtin_mips_set_fcsr(value); }
static unsigned exceptions(void) { return __builtin_mips_get_fcsr() & 0x7c; }

int main(void)
{
    unsigned saved = __builtin_mips_get_fcsr();
    quad zero = bits(0, 0), negative_zero = bits(0x8000000000000000ULL, 0);
    quad one = bits(0x3fff000000000000ULL, 0), two = bits(0x4000000000000000ULL, 0);
    quad three = bits(0x4000800000000000ULL, 0), half_ulp = bits(0x3f8e000000000000ULL, 0);
    quad infinity = bits(0x7fff000000000000ULL, 0);
    quad quiet_nan = bits(0x7fff400000000000ULL, 1);
    quad signaling_nan = bits(0x7fff800000000000ULL, 1);
    mode(0);
    same(__addtf3(one, two), 0x4000800000000000ULL, 0);
    same(__subtf3(one, two), 0xbfff000000000000ULL, 0);
    same(__multf3(three, two), 0x4001800000000000ULL, 0);
    same(__divtf3(three, two), 0x3fff800000000000ULL, 0);
    same(__divtf3(one, three), 0x3ffd555555555555ULL, 0x5555555555555555ULL);
    same(__negtf2(zero), 0x8000000000000000ULL, 0);
    same(__negtf2(negative_zero), 0, 0);
    same(__addtf3(negative_zero, negative_zero), 0x8000000000000000ULL, 0);
    same(__addtf3(one, half_ulp), 0x3fff000000000000ULL, 0);
    CHECK(exceptions() & 4);
    mode(2);
    same(__addtf3(one, half_ulp), 0x3fff000000000000ULL, 1);
    mode(3);
    same(__addtf3(one, half_ulp), 0x3fff000000000000ULL, 0);
    same(__subtf3(__negtf2(one), half_ulp), 0xbfff000000000000ULL, 1);
    same(__addtf3(one, __negtf2(one)), 0x8000000000000000ULL, 0);
    mode(1);
    same(__addtf3(one, half_ulp), 0x3fff000000000000ULL, 0);
    mode(0);
    same(__addtf3(bits(0x3fff000000000000ULL, 1), half_ulp), 0x3fff000000000000ULL, 2);
    same(__multf3(bits(0, 1), two), 0, 2);
    mode(0);
    same(__divtf3(bits(0, 1), two), 0, 0);
    CHECK(exceptions() == (8 | 4));
    mode(0);
    same(__multf3(bits(0x7ffeffffffffffffULL, UINT64_MAX), two), 0x7fff000000000000ULL, 0);
    CHECK(exceptions() == (16 | 4));
    mode(0);
    same(__divtf3(one, zero), 0x7fff000000000000ULL, 0);
    CHECK(exceptions() == 32);
    mode(0);
    CHECK(__unordtf2(__divtf3(zero, zero), one) != 0);
    CHECK(exceptions() == 64);
    mode(0);
    CHECK(__eqtf2(one, one) == 0 && __netf2(one, two) != 0);
    CHECK(__eqtf2(zero, negative_zero) == 0);
    CHECK(__letf2(one, two) < 0 && __lttf2(one, two) < 0);
    CHECK(__getf2(two, one) > 0 && __gttf2(two, one) > 0);
    CHECK(__letf2(one, one) == 0 && __getf2(one, one) == 0);
    CHECK(__unordtf2(infinity, one) == 0 && __unordtf2(quiet_nan, one) != 0);
    CHECK(exceptions() == 0);
    CHECK(__eqtf2(quiet_nan, quiet_nan) != 0);
    CHECK(exceptions() == 0);
    CHECK(__eqtf2(signaling_nan, one) != 0);
    CHECK(exceptions() == 64);
    mode(0);
    CHECK(__letf2(quiet_nan, one) > 0 && __getf2(quiet_nan, one) < 0);
    CHECK(exceptions() == 64);
    mode(0);
    same(__extendsftf2(1.5f), 0x3fff800000000000ULL, 0);
    same(__extenddftf2(-2.5), 0xc000400000000000ULL, 0);
    CHECK(__trunctfsf2(three) == 3.0f && __trunctfdf2(three) == 3.0);
    same(__floatsitf(-2147483647 - 1), 0xc01e000000000000ULL, 0);
    CHECK(__fixtfsi(__floatsitf(-2147483647 - 1)) == (-2147483647 - 1));
    CHECK(__fixunstfsi(__floatunsitf(UINT32_MAX)) == UINT32_MAX);
    same(__floatditf(INT64_MIN), 0xc03e000000000000ULL, 0);
    CHECK(__fixtfdi(__floatditf(INT64_MIN)) == INT64_MIN);
    CHECK(__fixunstfdi(__floatunditf(UINT64_MAX)) == UINT64_MAX);
    wide negative = -((wide)1 << 110) + 17;
    uwide positive = ((uwide)1 << 112) - 1;
    CHECK(__fixtfti(__floattitf(negative)) == negative);
    CHECK(__fixunstfti(__floatuntitf(positive)) == positive);
    same(__floatuntitf((uwide)1 << 127), 0x407e000000000000ULL, 0);
    CHECK(__fixunstfti(bits(0x407e000000000000ULL, 0)) == ((uwide)1 << 127));
    CHECK(__fixtfsi(__negtf2(__divtf3(three, two))) == -1);
    CHECK(__fixtfdi(__divtf3(three, two)) == 1);
    CHECK(__fixunstfsi(__divtf3(three, two)) == 1);
    CHECK(__fixunstfdi(__divtf3(three, two)) == 1);
    char text[256];
    mode(0);
    int count = snprintf(text, sizeof text, "%d %u %lld %llu %.2f %.3Lf %La",
        -17, 42u, -9223372036854775807LL, 18446744073709551615ULL, 1.25,
        __divtf3(three, two), one);
    CHECK(count > 0 && (size_t)count == strlen(text));
    CHECK(!strcmp(text, "-17 42 -9223372036854775807 18446744073709551615 1.25 1.500 0x1p+0"));
    CHECK(snprintf(text, sizeof text, "%.36Lg", __divtf3(one, three)) == 38);
    CHECK(!strcmp(text, "0.333333333333333333333333333333333317"));
    CHECK(snprintf(text, sizeof text, "%Lg %Lg %Lg", infinity, __negtf2(infinity), negative_zero) == 11);
    CHECK(!strcmp(text, "inf -inf -0"));
    char *end = 0;
    same(strtold("1.25tail", &end), 0x3fff400000000000ULL, 0);
    CHECK(end && !strcmp(end, "tail"));
    mode(saved);
    CHECK(printf("SOFTFP_PRINTF int=%d uint=%u double=%.2f quad=%.3Lf\n", -17, 42u, 1.25, __divtf3(three, two)) == 53);
    CHECK(fflush(stdout) == 0);
    const char success[] = "OK_MUSL_SOFTFP arithmetic=pass rounding=pass exceptions=pass comparisons=pass conversions=pass stdio=pass\n";
    CHECK(write(1, success, sizeof success - 1) == sizeof success - 1);
    return 0;
}
