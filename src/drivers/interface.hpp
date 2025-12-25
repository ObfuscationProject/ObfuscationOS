#ifndef DRIVER_INTERFACE_H
#define DRIVER_INTERFACE_H

#include <stddef.h>
#include <stdint.h>

// 驱动接口定义
namespace driver
{

// 设备类型
enum class DeviceType
{
    BLOCK_DEVICE,
    CHAR_DEVICE,
    NETWORK_DEVICE,
    USB_DEVICE
};

// 驱动操作
struct DriverOperations
{
    int (*open)(void *device, uint32_t flags);
    int (*close)(void *device);
    int (*read)(void *device, void *buffer, size_t count);
    int (*write)(void *device, const void *buffer, size_t count);
    int (*ioctl)(void *device, uint32_t cmd, void *arg);
};

// 设备信息
struct DeviceInfo
{
    const char *name;
    DeviceType type;
    DriverOperations *ops;
    void *private_data;
};

// 驱动接口类
class DriverInterface
{
  public:
    virtual ~DriverInterface() = default;

    // 驱动初始化
    virtual bool initialize() = 0;

    // 设备注册
    virtual bool register_device(DeviceInfo *device_info) = 0;

    // 设备卸载
    virtual bool unregister_device(const char *name) = 0;

    // 获取设备
    virtual void *get_device(const char *name) = 0;
};

// 驱动管理器
class DriverManager
{
  public:
    static DriverManager *get_instance();

    bool install_driver(DriverInterface *driver);
    bool uninstall_driver(DriverInterface *driver);
    void *find_device(const char *name);

  private:
    DriverManager();
    static DriverManager instance_;
    DriverInterface *drivers_[32]; // 最多支持32个驱动
    int driver_count_;
};

} // namespace driver

#endif // DRIVER_INTERFACE_H