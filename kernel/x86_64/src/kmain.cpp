#include "hal/console.hpp"

extern "C" void kernel_main() noexcept
{
    hal::console::clear();
    hal::console::write("Hello World from ObfuscationOS kernel!\n");

    for (;;)
    {
        asm volatile("hlt");
    }
}
