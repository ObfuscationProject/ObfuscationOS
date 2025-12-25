#include "../include/obflib.h"
#include "../kernel/interface.hpp"
#include "interface.hpp"

namespace driver
{

DriverManager DriverManager::instance_;

DriverManager::DriverManager() : driver_count_(0)
{
    for (int i = 0; i < 32; i++)
    {
        drivers_[i] = nullptr;
    }
}

DriverManager *DriverManager::get_instance()
{
    return &instance_;
}

bool DriverManager::install_driver(DriverInterface *driver)
{
    if (driver_count_ >= 32)
    {
        return false; // 驱动数量已达上限
    }

    if (!driver->initialize())
    {
        return false; // 驱动初始化失败
    }

    drivers_[driver_count_] = driver;
    driver_count_++;
    return true;
}

bool DriverManager::uninstall_driver(DriverInterface *driver)
{
    for (int i = 0; i < driver_count_; i++)
    {
        if (drivers_[i] == driver)
        {
            // TODO: 卸载驱动前的清理工作
            drivers_[i] = nullptr;

            // 移动后续驱动填补空位
            for (int j = i; j < driver_count_ - 1; j++)
            {
                drivers_[j] = drivers_[j + 1];
            }
            driver_count_--;
            return true;
        }
    }
    return false;
}

void *DriverManager::find_device(const char *name)
{
    for (int i = 0; i < driver_count_; i++)
    {
        if (drivers_[i])
        {
            void *device = drivers_[i]->get_device(name);
            if (device)
            {
                return device;
            }
        }
    }
    return nullptr;
}

} // namespace driver