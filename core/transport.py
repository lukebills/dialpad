"""Native HID and macOS libusb transport. Never reads keyboard input.

The HID programming interface must expose a 64-byte output report. Some 8890
firmwares expose only their input interfaces on macOS; those are deliberately
not used as a substitute. No driver is detached and no report-ID probe is sent.
"""
import ctypes as C
import ctypes.util
import os
import sys
import threading

VID, PID = 0x1189, 0x8890
_write_lock = threading.Lock()


class TransportError(RuntimeError):
    def __init__(self, message, packets_written=0):
        super().__init__(message)
        self.packets_written = packets_written


class _USB:
    """Raw interrupt-OUT transport for the non-boot HID configuration interface.

    libusb is bundled in packaged macOS builds. Enumeration reads descriptors
    only. Interface claiming happens on explicit Apply; kernel drivers are never
    detached, devices reset, or configurations changed.
    """
    def __init__(self):
        bundle_root = getattr(sys, '_MEIPASS', None)
        candidates = ([os.path.join(bundle_root, name) for name in
                       ('libusb-1.0.0.dylib', 'libusb-1.0.dylib')] if bundle_root else
                      ['/opt/homebrew/lib/libusb-1.0.dylib', '/usr/local/lib/libusb-1.0.dylib'])
        path = next((p for p in candidates if os.path.isfile(p)), None)
        if not path and not bundle_root:
            path = C.util.find_library('usb-1.0')
        if not path:
            raise TransportError('Raw USB programming needs bundled libusb. Use a packaged app or install libusb for development.')
        self.lib = C.CDLL(path)
        u8, u16, p = C.c_uint8, C.c_uint16, C.c_void_p
        class Device(C.Structure):
            _fields_ = [('length', u8), ('type', u8), ('usb', u16), ('cls', u8), ('sub', u8),
                        ('protocol', u8), ('packet', u8), ('vid', u16), ('pid', u16), ('version', u16),
                        ('manufacturer', u8), ('product', u8), ('serial', u8), ('configs', u8)]
        class Endpoint(C.Structure):
            _fields_ = [('length', u8), ('type', u8), ('address', u8), ('attributes', u8),
                        ('max_packet', u16), ('interval', u8), ('refresh', u8), ('synch', u8),
                        ('extra', p), ('extra_length', C.c_int)]
        class Alternate(C.Structure):
            _fields_ = [('length', u8), ('type', u8), ('number', u8), ('alt', u8), ('endpoints', u8),
                        ('cls', u8), ('sub', u8), ('protocol', u8), ('string', u8),
                        ('endpoint', C.POINTER(Endpoint)), ('extra', p), ('extra_length', C.c_int)]
        class Interface(C.Structure):
            _fields_ = [('alternates', C.POINTER(Alternate)), ('count', C.c_int)]
        class Config(C.Structure):
            _fields_ = [('length', u8), ('type', u8), ('total', u16), ('interfaces', u8), ('value', u8),
                        ('string', u8), ('attributes', u8), ('power', u8),
                        ('interface', C.POINTER(Interface)), ('extra', p), ('extra_length', C.c_int)]
        self.Device, self.Config = Device, Config
        self.init = _fn(self.lib, 'libusb_init', C.c_int, p)
        self.exit = _fn(self.lib, 'libusb_exit', None, p)
        self.getlist = _fn(self.lib, 'libusb_get_device_list', C.c_ssize_t, p, p)
        self.freelist = _fn(self.lib, 'libusb_free_device_list', None, p, C.c_int)
        self.descriptor = _fn(self.lib, 'libusb_get_device_descriptor', C.c_int, p, p)
        self.config = _fn(self.lib, 'libusb_get_config_descriptor', C.c_int, p, u8, p)
        self.freeconfig = _fn(self.lib, 'libusb_free_config_descriptor', None, p)
        self.bus = _fn(self.lib, 'libusb_get_bus_number', u8, p)
        self.address = _fn(self.lib, 'libusb_get_device_address', u8, p)
        self.open = _fn(self.lib, 'libusb_open', C.c_int, p, p)
        self.close = _fn(self.lib, 'libusb_close', None, p)
        self.claim = _fn(self.lib, 'libusb_claim_interface', C.c_int, p, C.c_int)
        self.release = _fn(self.lib, 'libusb_release_interface', C.c_int, p, C.c_int)
        self.interrupt = _fn(self.lib, 'libusb_interrupt_transfer', C.c_int, p, u8, p, C.c_int, p, C.c_uint)
        self.error = _fn(self.lib, 'libusb_error_name', C.c_char_p, C.c_int)

    def check(self, status, action, sent=0):
        if status < 0:
            raise TransportError(f'{action}: {self.error(status).decode()}. '
                                 + ('Hardware state may be partial; no automatic retry.' if sent else
                                    'No completed programming packets. Close other configurators and retry.'), sent)

    def visit(self, callback):
        context, devices = C.c_void_p(), C.POINTER(C.c_void_p)()
        self.check(self.init(C.byref(context)), 'Initialize USB')
        try:
            count = self.getlist(context, C.byref(devices))
            self.check(count, 'Enumerate USB')
            result = []
            for index in range(count):
                device = devices[index]
                desc = self.Device()
                if self.descriptor(device, C.byref(desc)) or (desc.vid, desc.pid) != (VID, PID) or desc.configs != 1:
                    continue
                config = C.POINTER(self.Config)()
                if self.config(device, 0, C.byref(config)):
                    continue
                try:
                    for pos in range(config.contents.interfaces):
                        interface = config.contents.interface[pos]
                        if interface.count != 1:
                            continue
                        alt = interface.alternates[0]
                        if (alt.cls, alt.sub, alt.protocol, alt.alt) != (3, 0, 0, 0):
                            continue
                        for epidx in range(alt.endpoints):
                            ep = alt.endpoint[epidx]
                            if ep.address != 2 or ep.attributes & 3 != 3 or ep.max_packet < 64:
                                continue
                            identifier = f'usb:{self.bus(device)}:{self.address(device)}:{alt.number}'
                            info = dict(id=identifier, device_id=identifier, vendor_id=VID, product_id=PID,
                                        product='Mini keyboard · USB configuration', platform=sys.platform,
                                        interface=alt.number, endpoint=2, output_report_bytes=64,
                                        programmable=True, transport_verified=False, transport='libusb',
                                        limitation='USB descriptors match the reference programmer. '
                                                   'Physical programming and persistence are not yet verified.')
                            result.append(callback(device, info))
                finally:
                    self.freeconfig(config)
            return result
        finally:
            if devices:
                self.freelist(devices, 1)
            self.exit(context)

    def send(self, identifier, packets):
        found, sent = False, 0
        def apply(device, info):
            nonlocal found, sent
            if info['id'] != identifier:
                return
            found = True
            handle = C.c_void_p()
            self.check(self.open(device, C.byref(handle)), 'Open USB configuration interface')
            claimed = False
            try:
                self.check(self.claim(handle, info['interface']), 'Claim USB configuration interface')
                claimed = True
                for packet in packets:
                    data, written = C.create_string_buffer(packet, 64), C.c_int()
                    status = self.interrupt(handle, 2, data, 64, C.byref(written), 1500)
                    self.check(status, 'Write USB packet', sent)
                    if written.value != 64:
                        raise TransportError(f'USB accepted only {written.value}/64 bytes. Hardware state may be partial.', sent)
                    sent += 1
            finally:
                if claimed:
                    self.release(handle, info['interface'])
                self.close(handle)
        self.visit(apply)
        if not found:
            raise TransportError('Selected USB device disconnected. Refresh devices and select it again.')
        return sent


def _fn(lib, name, result, *args):
    fn = getattr(lib, name)
    fn.restype, fn.argtypes = result, list(args)
    return fn


def _description(identifier, **props):
    eligible = props.get('output_report_bytes', 0) >= 64 and props.get('usage_page', 0) >= 0xFF00
    return dict(id=identifier, device_id=identifier, vendor_id=VID, product_id=PID,
                programmable=eligible, transport_verified=False,
                limitation=('Native HID programming is unverified on this device.' if eligible else
                            'This is an input interface, not an accessible programming interface. '
                            'The firmware may require raw USB access; no driver is installed or replaced.'), **props)


class _Mac:
    def __init__(self):
        self.cf = C.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
        self.io = C.CDLL('/System/Library/Frameworks/IOKit.framework/IOKit')
        p, n = C.c_void_p, C.c_long
        self.string = _fn(self.cf, 'CFStringCreateWithCString', p, p, C.c_char_p, C.c_uint32)
        self.release = _fn(self.cf, 'CFRelease', None, p)
        self.number = _fn(self.cf, 'CFNumberGetValue', C.c_bool, p, C.c_int, p)
        self.text = _fn(self.cf, 'CFStringGetCString', C.c_bool, p, p, n, C.c_uint32)
        self.create = _fn(self.io, 'IOHIDManagerCreate', p, p, C.c_uint32)
        self.match = _fn(self.io, 'IOHIDManagerSetDeviceMatching', None, p, p)
        self.copy = _fn(self.io, 'IOHIDManagerCopyDevices', p, p)
        self.count = _fn(self.cf, 'CFSetGetCount', n, p)
        self.values = _fn(self.cf, 'CFSetGetValues', None, p, p)
        self.prop = _fn(self.io, 'IOHIDDeviceGetProperty', p, p, p)
        self.service = _fn(self.io, 'IOHIDDeviceGetService', C.c_uint32, p)
        self.entryid = _fn(self.io, 'IORegistryEntryGetRegistryEntryID', C.c_int32, C.c_uint32, p)
        self.open = _fn(self.io, 'IOHIDDeviceOpen', C.c_int32, p, C.c_uint32)
        self.close = _fn(self.io, 'IOHIDDeviceClose', C.c_int32, p, C.c_uint32)
        self.write = _fn(self.io, 'IOHIDDeviceSetReport', C.c_int32, p, C.c_int, n, p, n)

    def property(self, device, name, string=False):
        key = self.string(None, name.encode(), 0x08000100)
        try:
            value = self.prop(device, key)
            if not value:
                return '' if string else 0
            if string:
                buf = C.create_string_buffer(1024)
                return buf.value.decode('utf-8', 'replace') if self.text(value, buf, len(buf), 0x08000100) else ''
            result = C.c_longlong()
            return result.value if self.number(value, 4, C.byref(result)) else 0
        finally:
            self.release(key)

    def visit(self, callback):
        manager = self.create(None, 0)
        devices = None
        try:
            self.match(manager, None)
            devices = self.copy(manager)
            if not devices:
                return []
            values = (C.c_void_p * self.count(devices))()
            self.values(devices, values)
            result = []
            for device in values:
                if self.property(device, 'VendorID') != VID or self.property(device, 'ProductID') != PID:
                    continue
                entry = C.c_uint64()
                if self.entryid(self.service(device), C.byref(entry)):
                    continue
                info = _description('mac:' + str(entry.value), product=self.property(device, 'Product', True),
                                    usage_page=self.property(device, 'PrimaryUsagePage'),
                                    usage=self.property(device, 'PrimaryUsage'),
                                    output_report_bytes=self.property(device, 'MaxOutputReportSize'),
                                    interface=None, platform='macos')
                result.append(callback(device, info))
            return result
        finally:
            if devices:
                self.release(devices)
            self.release(manager)

    def send(self, identifier, packets):
        sent = 0
        found = False
        def apply(device, info):
            nonlocal sent, found
            if info['id'] != identifier:
                return
            found = True
            if not info['programmable']:
                raise TransportError(info['limitation'])
            status = self.open(device, 0)  # kIOHIDOptionsTypeNone, never seize
            if status:
                raise TransportError(f'Non-exclusive HID open failed (0x{status & 0xffffffff:08x}).')
            try:
                for packet in packets:
                    # The encoder includes the report ID in its USB packet.
                    data = C.create_string_buffer(packet, len(packet))
                    status = self.write(device, 1, packet[0], data, len(packet))
                    if status:
                        raise TransportError(f'HID output failed (0x{status & 0xffffffff:08x}); '
                                             'the firmware may require an interrupt USB endpoint. '
                                             'Hardware state may be partial.', sent)
                    sent += 1
            finally:
                self.close(device, 0)
        self.visit(apply)
        if not found:
            raise TransportError('Selected device disconnected. Refresh devices and select it again.')
        return sent


class _Windows:
    def __init__(self):
        from ctypes import wintypes as W
        self.W = W
        self.hid = C.WinDLL('hid', use_last_error=True)
        self.setup = C.WinDLL('setupapi', use_last_error=True)
        self.kernel = C.WinDLL('kernel32', use_last_error=True)
        class GUID(C.Structure):
            _fields_ = [('a', W.DWORD), ('b', W.WORD), ('c', W.WORD), ('d', W.BYTE * 8)]
        class Interface(C.Structure):
            _fields_ = [('size', W.DWORD), ('guid', GUID), ('flags', W.DWORD), ('reserved', C.c_size_t)]
        class Attributes(C.Structure):
            _fields_ = [('size', W.ULONG), ('vid', W.USHORT), ('pid', W.USHORT), ('version', W.USHORT)]
        class Caps(C.Structure):
            _fields_ = [('usage', W.USHORT), ('page', W.USHORT), ('input', W.USHORT),
                        ('output', W.USHORT), ('feature', W.USHORT), ('reserved', W.USHORT * 17),
                        ('counts', W.USHORT * 10)]
        class Overlapped(C.Structure):
            _fields_ = [('internal', C.c_size_t), ('internal_high', C.c_size_t),
                        ('offset', W.DWORD), ('offset_high', W.DWORD), ('event', W.HANDLE)]
        self.GUID, self.Interface, self.Attributes, self.Caps, self.Overlapped = GUID, Interface, Attributes, Caps, Overlapped
        p = C.c_void_p
        self.guid = _fn(self.hid, 'HidD_GetHidGuid', None, p)
        self.get = _fn(self.setup, 'SetupDiGetClassDevsW', W.HANDLE, p, W.LPCWSTR, W.HWND, W.DWORD)
        self.enum = _fn(self.setup, 'SetupDiEnumDeviceInterfaces', W.BOOL, W.HANDLE, p, p, W.DWORD, p)
        self.detail = _fn(self.setup, 'SetupDiGetDeviceInterfaceDetailW', W.BOOL, W.HANDLE, p, p, W.DWORD, p, p)
        self.destroy = _fn(self.setup, 'SetupDiDestroyDeviceInfoList', W.BOOL, W.HANDLE)
        self.open = _fn(self.kernel, 'CreateFileW', W.HANDLE, W.LPCWSTR, W.DWORD, W.DWORD, p, W.DWORD, W.DWORD, W.HANDLE)
        self.close = _fn(self.kernel, 'CloseHandle', W.BOOL, W.HANDLE)
        self.attrs = _fn(self.hid, 'HidD_GetAttributes', C.c_ubyte, W.HANDLE, p)
        self.preparsed = _fn(self.hid, 'HidD_GetPreparsedData', C.c_ubyte, W.HANDLE, p)
        self.free = _fn(self.hid, 'HidD_FreePreparsedData', C.c_ubyte, p)
        self.caps = _fn(self.hid, 'HidP_GetCaps', C.c_int32, p, p)
        self.write = _fn(self.kernel, 'WriteFile', W.BOOL, W.HANDLE, p, W.DWORD, p, p)
        self.event = _fn(self.kernel, 'CreateEventW', W.HANDLE, p, W.BOOL, W.BOOL, W.LPCWSTR)
        self.wait = _fn(self.kernel, 'WaitForSingleObject', W.DWORD, W.HANDLE, W.DWORD)
        self.result = _fn(self.kernel, 'GetOverlappedResult', W.BOOL, W.HANDLE, p, p, W.BOOL)
        self.cancel = _fn(self.kernel, 'CancelIoEx', W.BOOL, W.HANDLE, p)
        self.invalid = C.c_void_p(-1).value

    def devices(self):
        guid = self.GUID()
        self.guid(C.byref(guid))
        handle = self.get(C.byref(guid), None, None, 0x12)
        if handle == self.invalid:
            raise TransportError(f'HID enumeration failed: {C.get_last_error()}')
        devices = []
        try:
            index = 0
            while True:
                interface = self.Interface()
                interface.size = C.sizeof(interface)
                if not self.enum(handle, None, C.byref(guid), index, C.byref(interface)):
                    if C.get_last_error() != 259:
                        raise TransportError(f'HID interface enumeration failed: {C.get_last_error()}')
                    break
                index += 1
                required = self.W.DWORD()
                self.detail(handle, C.byref(interface), None, 0, C.byref(required), None)
                if required.value < 8 or required.value > 65536:
                    continue
                detail = C.create_string_buffer(required.value)
                C.cast(detail, C.POINTER(self.W.DWORD))[0] = 8 if C.sizeof(C.c_void_p) == 8 else 6
                if not self.detail(handle, C.byref(interface), detail, len(detail), None, None):
                    continue
                path = C.wstring_at(C.addressof(detail) + 4)
                if 'vid_1189&pid_8890' not in path.lower():
                    continue
                native = self.open(path, 0, 3, None, 3, 0, None)
                if native == self.invalid:
                    continue
                try:
                    attrs = self.Attributes()
                    attrs.size = C.sizeof(attrs)
                    if not self.attrs(native, C.byref(attrs)) or (attrs.vid, attrs.pid) != (VID, PID):
                        continue
                    caps, prep = self.Caps(), C.c_void_p()
                    if self.preparsed(native, C.byref(prep)):
                        try:
                            self.caps(prep, C.byref(caps))
                        finally:
                            self.free(prep)
                    info = _description('win:' + path, product='Mini keyboard', usage_page=caps.page,
                                        usage=caps.usage, output_report_bytes=caps.output, platform='windows',
                                        interface=1 if 'mi_01' in path.lower() else None)
                    # Only the vendor interface is a configuration candidate.
                    info['programmable'] = info['programmable'] and info['interface'] == 1
                    devices.append(info)
                finally:
                    self.close(native)
        finally:
            self.destroy(handle)
        return devices

    def send(self, identifier, packets):
        info = next((d for d in self.devices() if d['id'] == identifier), None)
        if not info:
            raise TransportError('Selected device disconnected. Refresh devices and select it again.')
        if not info['programmable']:
            raise TransportError(info['limitation'])
        if info['output_report_bytes'] != 65:
            raise TransportError('This firmware has an unsupported HID report size; nothing was written.')
        native = self.open(identifier[4:], 0x40000000, 3, None, 3, 0x40000000, None)
        if native == self.invalid:
            raise TransportError(f'Could not open programming interface: Windows error {C.get_last_error()}.')
        sent = 0
        try:
            for packet in packets:
                # Already contains report ID 3. Windows requires the entire
                # declared report size; append padding, never a second ID.
                buffer = C.create_string_buffer(packet.ljust(65, b'\x00'), 65)
                count = self.W.DWORD()
                operation = self.Overlapped()
                operation.event = self.event(None, True, False, None)
                if not operation.event:
                    raise TransportError('Could not allocate HID write event.', sent)
                try:
                    ok = self.write(native, buffer, 65, C.byref(count), C.byref(operation))
                    if not ok and C.get_last_error() == 997:
                        if self.wait(operation.event, 1500) != 0:
                            self.cancel(native, C.byref(operation))
                            # Drain the canceled operation before releasing its buffers.
                            self.result(native, C.byref(operation), C.byref(count), True)
                            raise TransportError('HID output timed out. Hardware state may be partial.', sent)
                        ok = self.result(native, C.byref(operation), C.byref(count), False)
                    if not ok or count.value != 65:
                        raise TransportError(f'HID output failed: Windows error {C.get_last_error()}. '
                                             'Hardware state may be partial.', sent)
                    sent += 1
                finally:
                    self.close(operation.event)
        finally:
            self.close(native)
        return sent


def _backend():
    if sys.platform == 'darwin':
        return _Mac()
    if sys.platform == 'win32':
        return _Windows()
    raise TransportError('Native HID access is implemented for macOS and Windows only.')


def list_devices():
    backend = _backend()
    devices = backend.visit(lambda device, info: info) if sys.platform == 'darwin' else backend.devices()
    if sys.platform == 'darwin':
        try:
            devices = _USB().visit(lambda device, info: info) + devices
        except (TransportError, OSError):
            # Native HID enumeration remains available without bundled libusb.
            for device in devices:
                device['limitation'] += ' Raw USB library unavailable; use the packaged application.'
    return devices


def write_packets(device_id: str, packets: list[bytes]) -> dict:
    """Explicit write only. Failure carries packets_written; no retry or rollback."""
    if not isinstance(device_id, str) or not device_id:
        raise TransportError('Select a device first.')
    if not isinstance(packets, list) or not packets or len(packets) > 1024:
        raise TransportError('Expected 1–1024 packets.')
    if any(not isinstance(packet, bytes) or len(packet) != 64 for packet in packets):
        raise TransportError('Every protocol packet must be exactly 64 bytes.')
    raw_usb = device_id.startswith('usb:') and sys.platform == 'darwin'
    if any(packet[0] != 3 and not (index == 0 and packet == bytes(64))
           for index, packet in enumerate(packets)):
        raise TransportError('Native HID requires report ID 3 packets. Raw USB initialization packets '
                             'cannot be sent with this transport; nothing was written.')
    # The upstream raw-USB initialization is not a HID report and native HID
    # must not probe report ID zero. Both transports share the same caller API.
    if not raw_usb and packets[0] == bytes(64):
        packets = packets[1:]
    if not packets or all(packet == bytes(64) for packet in packets):
        raise TransportError('No programming reports supplied; nothing was written.')
    if not _write_lock.acquire(blocking=False):
        raise TransportError('Another device write is already running.')
    try:
        count = (_USB() if raw_usb else _backend()).send(device_id, packets)
        return dict(packets_written=count, verified=False,
                    message='Output reports sent. Test the physical controls; hardware read-back is unavailable.')
    finally:
        _write_lock.release()
