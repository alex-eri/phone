#!/usr/bin/python2
#coding: utf8

# Requirements
#python2-pyseria
#gstreamer0.10-python

import os
import sys

sys.argv[0]='Phone Manager'

import gobject
import dbus
import dbus.service
import dbus.glib
import threading

gobject.threads_init()

import serial
import time

STATE_NOT_MANAGED=0
STATE_LISTENING=10
STATE_RINGING=20
STATE_CALLING=30
STATE_CONNECTED=40


import audiodrv

class mmInterface(dbus.Interface):
    def __init__(self,path,dbus_interface):
        bus = dbus.SystemBus()
        manager_proxy = bus.get_object('org.freedesktop.ModemManager', path)
        dbus.Interface.__init__(self,manager_proxy, dbus_interface)

bus_name = dbus.service.BusName('su.eerie.PhoneManager', bus = dbus.SessionBus())

import glob

# paterns to determinate audio interface
vendor2audioif ={
'ZTE CORPORATION':'/*.2/tty*',
'huawei':'/*.1/tty*',
'ZTE INCORPORATED':'/*.2/tty*'
}

def GetAudioIf(masterDevice,vendor):
    #~ print masterDevice
    try:
        tty='/dev/' + glob.glob(masterDevice+vendor2audioif[vendor])[0].split('/')[-1]
    except:
        tty='/dev/null'
    return tty

# paterns to determinate at interface with indicators
vendor2atif ={
'ZTE CORPORATION':'/*.3/tty*',
'huawei':'/*.2/tty*',
#'ZTE INCORPORATED':'/*.3/tty*'
}

#ZTE INCORPORATED - mf626

def GetATIf(masterDevice,vendor):
    #~ print masterDevice
    try:
        tty='/dev/' + glob.glob(masterDevice+vendor2atif[vendor])[0].split('/')[-1]
    except:
        tty='/dev/null'
    return tty

class MyDevice(dbus.service.Object):
    INIT=[
        'ATE0', #disable echo
        'AT+CLIP=1', #enable caller id-ion
        'AT^CVOICE=0', #huawei
        #'AT+CLVL=4' # OK, but not make sence 
        ]
    def __init__(self,path):
        self.State=0
        self.Abonent = ''
        

        
        dbus.service.Object.__init__(self, bus_name, path)
        self.modem=mmInterface(path,'org.freedesktop.ModemManager.Modem')
        self.props=mmInterface(path, dbus_interface='org.freedesktop.DBus.Properties')

        self.info = self.modem.GetInfo()
        vendor = str(self.info[0])
        print ' '.join(self.info)
        
        atTty=str(GetATIf(self.props.Get('org.freedesktop.ModemManager.Modem', 'MasterDevice'),vendor))
        if atTty == '/dev/null':
            atTty=str('/dev/'+self.props.Get('org.freedesktop.ModemManager.Modem', 'Device'))
        
        print 'AT',atTty
        self.serial = serial.Serial()
        self.serial.port = atTty
        self.serial.timeout = 1
    
        thrAT = threading.Thread(target=self._readlines)
        thrAT.setDaemon(True)
        thrAT.start()
        
        voiceTty=str(GetAudioIf(self.props.Get('org.freedesktop.ModemManager.Modem', 'MasterDevice'),vendor))
        print "VOICE", voiceTty
        self.audio = audiodrv.AudioDrivers[vendor](voiceTty)

        self.modem.connect_to_signal('StateChanged',self.mmStateCalback)
        
        time.sleep(5) #wait for MM stop initialisation and maybe release port
        mmstate = self.props.Get('org.freedesktop.ModemManager.Modem', 'State')     
        self.mmStateCalback(None,mmstate,None)
        
        self.initModem()
    
    def initModem(self):
        for cmd in self.INIT:
            self.write('%s\r'%cmd)
    
    def voiceOn(self):
        if str(self.info[0]) == 'huawei' : self.serial.write('AT^DDSETEX=2\r')
        self.audio.start()
    def voiceOff(self):
        self.audio.stop()
                    
    @dbus.service.signal(dbus_interface='su.eerie.PhoneManager.Voice')
    def Connect(self):
        #ringtone off
        self.State=STATE_CONNECTED
        self.voiceOn()
        
                    
    @dbus.service.signal(dbus_interface='su.eerie.PhoneManager.Voice')
    def Ring(self):
        #ringtone on    
        self.State =STATE_RINGING
        print "signal:RING"

    @dbus.service.signal(dbus_interface='su.eerie.PhoneManager.Voice',signature='s')
    def CallerID(self,id):
        self.Abonent = id
        print "signal:CallerID"

    @dbus.service.signal(dbus_interface='su.eerie.PhoneManager.Voice')
    def StopRing(self):
        #ringtone off
        self.State = STATE_LISTENING
        self.Abonent = ''   
        print "signal:STOPRING"

    @dbus.service.signal(dbus_interface='su.eerie.PhoneManager.Voice')
    def Ringback(self):
        self.voiceOn()
        #conected on
        self.State = STATE_CALLING
        #voice on   
        print "signal:RINGBACK"

    @dbus.service.signal(dbus_interface='su.eerie.PhoneManager.Voice',signature='u')
    def Hold(self,reason):
        #voice off
        self.voiceOff() 
        self.State = STATE_LISTENING
        self.Abonent = ''
        print "signal:hold", reason

                        
    def _parse(self,indicate):

        def parsehold(indicate):
            try:
                code = int(indicate.split(":")[1])
            except:
                code = 0
            self.Hold(code)         
            if self.State == STATE_RINGING : self.StopRing()

        indicate=indicate.strip()
        if indicate == 'RING' : self.Ring()
        elif indicate[:16] == 'VOICE NO CARRIER' :      parsehold(indicate)
        elif indicate == 'VOICE CONNECT':               self.Connect() #zte
        elif indicate == 'STOPRING' : self.StopRing()
        elif indicate == 'RINGBACK' : self.Ringback()
        elif indicate == 'NO CARRIER' : self.Hold(0)
        elif indicate == 'ANSWER' : self.Connect()
        elif indicate[:5] == '^CONN' : self.Connect() #huawei
        elif indicate[:6] == 'HANGUP' : parsehold(indicate)
        elif indicate[:5] == '^CEND' : parsehold(indicate) #huawei
        elif indicate[:5] == '+CLIP' :
            try:
                self.CallerID( indicate.split(':')[1].split(',')[0].replace('"',''))
            except:
                self.Abonent = ''
        elif indicate[:5] == '^CONF' : self.Ringback() #huawei
        
        if indicate : print '<<',indicate
        #print ".",
    
    def _readlines(self):
        while True:
            if self.State and self.serial.isOpen():
                #~ try:
                    self._parse(self.serial.readline())
                #~ except:
                    #~ print "at port err"
                    #~ self.controled=False
                    #~ self.serial.close()
            else:
                time.sleep(3)
    def write(self,command):
        print '>>',command
        self.serial.write('%s\r'%command)
        
            
    def mmStateCalback(self,old,new,reason):
        if new == 10:
            self.serial.open()
            self.State = STATE_LISTENING
        else:
            self.State = STATE_NOT_MANAGED
            self.serial.close()
        #~ print old,new,reason
        
        
    @dbus.service.method(dbus_interface='su.eerie.PhoneManager.Voice', in_signature='s',out_signature='')
    def Dial(self,number):
        if self.State :
            if self.State >= STATE_CALLING :
                self.write('ATDT%s\r'%number) #"AT^DTMF=%d,%c\r", cpvt->call_idx, digit
                print 'tone %s' % number
            elif number[-1]=='#':
                pass
            else:
                self.write('ATD%s;\r'%number)
                self.Abonent = number
                print 'calling %s' % number

        return None

        
    @dbus.service.method(dbus_interface='su.eerie.PhoneManager.Voice', in_signature='',out_signature='')
    def Answer(self):
        if self.State == STATE_RINGING:
            self.write('ATA\r')
            print 'answered'
        #self.voiceOn()
        return None

    
    @dbus.service.method(dbus_interface='su.eerie.PhoneManager.Voice', in_signature='',out_signature='')
    def Hangup(self):
        if self.State >= STATE_RINGING :
            self.write('AT+CHUP\r')
        self.Abonent = ''
        print 'hangup'
        self.voiceOff()
        return None

        
    def remove(self):
        if self.State : self.serial.close() 
        if self.State == STATE_RINGING : self.StopRing()
        if self.State >= STATE_CALLING : self.Hold(-1)
        self.remove_from_connection()
        del self
    

    @dbus.service.signal (dbus_interface = dbus.PROPERTIES_IFACE, signature = 'sa{sv}as') # pylint: disable-msg=C0103
    def PropertiesChanged (self, interface_name, changed_properties, invalidated_properties):
        pass
    

        
    @dbus.service.method (dbus_interface = dbus.PROPERTIES_IFACE,
                        in_signature = 'ss', # pylint: disable-msg=C0103
                        out_signature = 'v')
    def Get (self, interface_name, property_name):
        return self.GetAll(interface_name)[property_name]
        
    @dbus.service.method (dbus_interface = dbus.PROPERTIES_IFACE,
                        in_signature = 's', # pylint: disable-msg=C0103
                        out_signature = 'a{sv}')
    def GetAll(self, interface_name):
        if interface_name == 'su.eerie.PhoneManager.Voice':
            return {
                'State':self.State,
                'Abonent':self.Abonent
                }
        else :
            return {}


class MyDBUSService(dbus.service.Object):
    def __init__(self):
        
        dbus.service.Object.__init__(self, bus_name, '/su/eerie/PhoneManager')
        
        self.modemmanager = mmInterface('/org/freedesktop/ModemManager','org.freedesktop.ModemManager')
        self.modemmanager.connect_to_signal('DeviceAdded',self.DeviceAdded)
        self.modemmanager.connect_to_signal('DeviceRemoved',self.DeviceRemoved)

        self.devices={}
        self.RescanDevices()
    
    @dbus.service.signal(dbus_interface='su.eerie.PhoneManager',signature='o')
    def DeviceAdded(self,path):
        self.devices[path]=MyDevice(path)

    @dbus.service.signal(dbus_interface='su.eerie.PhoneManager',signature='o')
    def DeviceRemoved(self,path):
        self.devices[path].remove()
        del self.devices[path]

    @dbus.service.method(dbus_interface='su.eerie.PhoneManager' )
    def RescanDevices(self):
        # Get available modems:
        for dev in self.devices.keys() :
            self.DeviceRemoved(dev)

        devices = self.modemmanager.EnumerateDevices()
        for dev in devices:
            self.DeviceAdded(dev)


    @dbus.service.method(dbus_interface='su.eerie.PhoneManager', out_signature='ao')
    def EnumerateDevices(self):
        return self.devices.keys()

if __name__ == '__main__':
    sharepath = os.path.expanduser("~/.local/share/PhoneManager/")
    
    pidfile = os.path.join(sharepath,"daemon.pid")

    EXIT=False
    if os.path.isfile(pidfile):
        pid=file(pidfile, 'r').readline().strip()
        try:
            pid=int(pid)
            EXIT=os.getpgid(pid)
        except:
            pass

    if EXIT:
        print "PhoneManager (pid %d) already running, exiting" % pid
        sys.exit()

    pid = str(os.getpid())
    if not os.path.isdir(sharepath):
        os.makedirs(sharepath)
    file(pidfile, 'w').write(pid)
            
    myservice = MyDBUSService()
    loop = gobject.MainLoop()
    loop.run()