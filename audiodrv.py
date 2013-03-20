#!/usr/bin/env python

import pygst, threading, gobject, time
pygst.require("0.10") 
import gst 
import serial

#gobject.threads_init()

_datalock = threading.Lock()
_data = ''
_dataevent = threading.Event()


ZTE_RECPIPE = '''gconfaudiosrc !
		capsfilter caps=audio/x-mulaw,rate=8000,channels=1 ! 
		fakesink name=sink signal-handoffs=true'''
		
#AT+CLVL=5
	
ZTE_PLAYPIPE = '''appsrc name=source !
		audio/x-mulaw,rate=8000,channels=1 !
		mulawdec !
		audioamplify amplification=15.0 !
		gconfaudiosink'''


#huawei
#  Encoding: Signed PCM    
#  Channels: 1 @ 16-bit   
#  Samplerate: 8000Hz  


HUAWEI_RECPIPE = '''gconfaudiosrc !
  capsfilter caps=audio/x-raw-int,width=16,depth=16,channels=1,rate=8000,signed=true,endianness=1234 !
  fakesink name=sink signal-handoffs=true'''
	
HUAWEI_PLAYPIPE = '''appsrc name=source !
  audio/x-raw-int, width=16, depth=16, channels=1, rate=8000, signed=true , endianness=1234 !
  audioamplify amplification=15.0 !
  gconfaudiosink'''


class Audio():
	BUFSIZE  = 160
	RATE=8000
	def __init__(self,port,baudrate=115200):
		self._setupport(port,baudrate)
		self.init2()

		self._caps = gst.caps_from_string(self.CAPS)

		#self.readbuff = ''
		self.producting = False
		
		self.playpipe = gst.parse_launch(self.PLAYPIPE)
		self.recpipe = gst.parse_launch(self.RECPIPE)

		self.source = self.playpipe.get_by_name("source") 
		self.recpipe.get_by_name('sink').connect('handoff', self._handoff)
		
		thrReader = threading.Thread(target=self._reader)
		thrReader.setDaemon(True)
		thrReader.start()
		
		print self.driver
	def init2(self):
		pass	
	def _setupport(self,port,baudrate=115200,timeout=1):
		self.port = serial.Serial()
		self.port.port = port
		self.port.baudrate = baudrate
		self.port.timeout = timeout
		
				
	def _handoff(self,element,buf,pad):
		global _datalock, _dataevent
		#_datalock.acquire()
		if self.producting :
			self.port.write(buf.data)
		#_dataevent.set()
		#_datalock.release()
		#print 'handoff' 
	
	def _push(self,data):
		buf = gst.Buffer(data)
		buf.set_caps(self._caps)
		buf.duration = len(data) * gst.SECOND / self.RATE
		self.source.emit('push-buffer', buf)

	def _reader(self):
		bps  = self.port.baudrate
		while True:
			if self.producting:
				readbuff = self.port.read(self.BUFSIZE)
				self._push(readbuff)
				#print self.producting
				# buf = gst.Buffer(readbuff)
				# buf.set_caps(caps)
				# self.source.emit('push-buffer', buf)
			else:
				time.sleep(1)
				
				#~ print '1',

	def start(self):
		print 'auio start'
		if not self.producting:
			self.port.open()
			self.port.flush()
			self.playpipe.set_state(gst.STATE_PLAYING)
			self.producting = True
			self.recpipe.set_state(gst.STATE_PLAYING)


	def stop(self):
		print 'audio stop'
		if self.producting:
			self.recpipe.set_state(gst.STATE_NULL)#(gst.STATE_PAUSED)				
			self.producting = False
			self.port.close()
			self.playpipe.set_state(gst.STATE_NULL)#(gst.STATE_PAUSED)



class ZTEAudio(Audio):
	driver = 'ZTE CORPORATION'
	CAPS='audio/x-mulaw,rate=8000,channels=1'
	PLAYPIPE = ZTE_PLAYPIPE
	RECPIPE  = ZTE_RECPIPE
	BUFSIZE  = 2048



class HuaweiAudio(Audio):
	driver = 'huawei'
	CAPS = 'audio/x-raw-int, width=16, depth=16, channels=1, rate=8000, signed=true , endianness=1234'
	PLAYPIPE = HUAWEI_PLAYPIPE
	RECPIPE  = HUAWEI_RECPIPE
	_recdata = ''
	BUFSIZE  = 320 #CVOICE:0,8000,16,20 -> 8000*(20/1000)*(16/8)=320 #frame size
	
	def init2(self):
		self.port.setBaudrate(230400)

	#~ def _handoff(self,element,buf,pad):
		#~ global _datalock, _dataevent
		#~ if self.producting :
			#~ _datalock.acquire()
			#~ self._recdata += buf.data
			#~ #_dataevent.set()
			#~ _datalock.release()
			#~ #print len(buf.data)
			#~ while len(self._recdata) >= self.BUFSIZE : #CVOICE:0,8000,16,20 -> 8000*(20/1000)*(16/8)=320 #frame size
				#~ self.port.write(self._recdata[:self.BUFSIZE])
				#~ self._recdata=self._recdata[self.BUFSIZE:]
		#~ #print 'handoff' 


AudioDrivers ={
	'ZTE CORPORATION':	ZTEAudio,
	'huawei':		HuaweiAudio,
	'ZTE INCORPORATED':	ZTEAudio,	
}

if __name__ == "__main__": 
	import sys
	au = AudioDrivers['ZTE CORPORATION'](sys.argv[1])
	au.start()

	loop = gobject.MainLoop()
	threading.Thread(target=loop.run).start()

