#!/usr/bin/python2
#coding: utf8

import dbus
import dbus.mainloop.glib
dbus.mainloop.glib.threads_init()

# import gobject
# gobject.threads_init()

dbusloop = dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
#loop = gobject.MainLoop()

class pmInterface(dbus.Interface):
    def __init__(self,path,dbus_interface):
        bus = dbus.SessionBus()
        manager_proxy = bus.get_object('su.eerie.PhoneManager', path)
        dbus.Interface.__init__(self,manager_proxy, dbus_interface)


import pygtk
import gtk


class Phone:
    def answer(self):
        self.interface.Answer()
    def hangup(self):
        self.interface.Hangup()

    def ring(self):
        self.parent.ring(self.path)

    def stopring(self):
        self.parent.stopring(self.path)

    def __init__(self,parent,path):
        self.parent     = parent
        self.path       = path
        self.interface  = pmInterface(path,'su.eerie.PhoneManager.Voice')
        self.interface.connect_to_signal('Ring', self.ring)
        self.interface.connect_to_signal('CallerID', self.parent.callerid)
        self.interface.connect_to_signal('Connect', self.parent.connect)

    def __del__(self):
        del self.interface



class Gui:
    phones = {}
    cid = ''
    ringer = ''
    def connectDevice(self,path):
        self.phones[path]=Phone(self,path)

    def removeDevice(self,path):
        del self.phones[path]

    def callerid(self, cid):
        self.cid=cid
        self.lCallerID.set_text('%s ringing'%cid)

    def ring(self, path):
        self.ringer = self.phones[path]
        if not self.cid: self.lCallerID.set_text('Ringing')

    def stopring(self, path):
        if self.cid : self.lCallerID.set_text("%s skipped"%self.cid)
        self.ringer = None
        self.cid=''

    def answer(self, widget, data=None):
        print 'answer'
        if self.ringer: self.ringer.answer()

    def connect(self):
        if self.cid : self.lCallerID.set_text("%s on call"%self.cid)

    def hangup(self, widget, data=None):
        if self.ringer: self.ringer.hangup()
        self.lCallerID.set_text('')

    def delete_event(self, widget, event, data=None):
        return False


    def destroy(self, widget, data=None):
        gtk.main_quit()

    def __init__(self):

        self.manager = pmInterface('/su/eerie/PhoneManager','su.eerie.PhoneManager')
        
        for phone in self.manager.EnumerateDevices(): self.connectDevice(phone)
        self.manager.connect_to_signal('DeviceAdded',self.connectDevice)
        self.manager.connect_to_signal('DeviceRemoved',self.removeDevice)

        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window
        self.window.connect("delete_event", self.delete_event)
        self.window.connect("destroy", self.destroy)
        self.window.set_border_width(10)

        boxIncomming = gtk.HBox(False, 5)

        self.lCallerID = gtk.Label('')

        bAnswer = gtk.Button("Answer")
        bAnswer.connect("clicked", self.answer, None)
        
        bHangup = gtk.Button("Hangup")
        bHangup.connect("clicked", self.hangup, None)

        boxIncomming.pack_start(self.lCallerID,True)
        boxIncomming.pack_start(bAnswer,False)
        boxIncomming.pack_start(bHangup,False)
        
        self.window.add(boxIncomming)

        bAnswer.show()
        bHangup.show()
        self.lCallerID.show()
        boxIncomming.show()

        self.window.set_default_size(300,-1)
        self.window.show()

        w,h = self.window.get_size()
        self.window.set_geometry_hints(boxIncomming,w,h)

        

    def main(self):
        gtk.main()




gui=Gui()
gui.main()

#loop.run()