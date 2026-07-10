import hid

for device in hid.enumerate():
    if device['vendor_id'] == 0x0483:
        print(f"Device Found: {device['product_string']}")
        print(f"Vendor ID: {hex(device['vendor_id'])}")
        print(f"Product ID: {hex(device['product_id'])}")
