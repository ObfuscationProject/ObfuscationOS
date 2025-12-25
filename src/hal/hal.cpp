#include "interface.hpp"
#include "x86_64.hpp"

namespace hal
{

HALInterface *get_hal()
{
#ifdef __x86_64__
    static x86_64::X86_64HAL hal_instance;
    return &hal_instance;
#else
    // 其他架构的实现
    return nullptr;
#endif
}

} // namespace hal