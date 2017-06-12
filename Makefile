DEVPATH='/sys/bus/usb/devices/3-2.1'
VALA_PACKAGES= --pkg gio-2.0 --pkg gee-0.8 --pkg posix

server: server.vala
	valac $(VALA_PACKAGES) $^ -o $@

test: server
	dbus-send --print-reply --system --dest=su.eerie.Phone /su/eerie/phone su.eerie.PhoneManager.AddBySyspath string:'${DEVPATH}'
	
