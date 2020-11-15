from RtpPacket import RtpPacket
import os
import traceback
import sys
import threading
import socket
from PIL import ImageTk
import PIL.Image

from time import time

from tkinter import *
import tkinter.messagebox
tkMessageBox = tkinter.messagebox


CACHE_FILE_NAME = "cache-"
CACHE_FILE_EXT = ".jpg"


class Client:

	SETUP = 'SETUP'
	PLAY = 'PLAY'
	PAUSE = 'PAUSE'
	TEARDOWN = 'TEARDOWN'
	DESCRIBE = 'DESCRIBE'

	INIT = 0
	READY = 1
	PLAYING = 2
	state = INIT

	# Initiation..
	def __init__(self, master, serverAddr, serverPort, rtpPort, fileName):

		self.master = master
		self.master.protocol("WM_DELETE_WINDOW", self.handler)
		self.createWidgets()

		self.serverAddr = serverAddr
		self.serverPort = int(serverPort)
		self.rtpPort = int(rtpPort)
		self.fileName = fileName

		self.connect()

		self.rtspSeq = 0
		self.sessionID = 0

		self.sentRequest = -1

		self.isTearDowned = False

		self.requestTemp = "{0} {1} RTSP/1.0\nCSeq: {2}\nSession: {3}"


		# self.connectToServer()

		self.frameNbr = 0

	def createWidgets(self):
		"""Build GUI."""
	
		# Create Setup button
		self.setup = Button(self.master, width=20, padx=3, pady=3)
		self.setup["text"] = "Setup"
		self.setup["command"] = self.setupMovie
		self.setup.grid(row=1, column=0, padx=2, pady=2)


		# Create Play button
		self.start = Button(self.master, width=20, padx=3, pady=3)
		self.start["text"] = "Play"
		self.start["command"] = self.playMovie
		self.start.grid(row=1, column=1, padx=2, pady=2)

		# Create Pause button
		self.pause = Button(self.master, width=20, padx=3, pady=3)
		self.pause["text"] = "Pause"
		self.pause["command"] = self.pauseMovie
		self.pause.grid(row=1, column=2, padx=2, pady=2)


		# Create Teardown button
		self.teardown = Button(self.master, width=20, padx=3, pady=3)
		self.teardown["text"] = "Teardown"
		self.teardown["command"] = self.tearDown
		self.teardown.grid(row=1, column=3, padx=2, pady=2)

		# Create Describe button
		self.describe = Button(self.master, width=20, padx=3, pady=3)
		self.describe["text"] = "Describe"
		self.describe["command"] = self.describeReq
		self.describe.grid(row=1, column=4, padx=2, pady=2)

		# Create a label to display the movie
		self.label = Label(self.master, height=19)
		self.label.grid(row=0, column=0, columnspan=5,
						sticky=W+E+N+S, padx=20, pady=5)
        
		# Statistics
		self.rcv = 0
		self.rcvStr = StringVar()
		self.label_data = Label(self.master, height=1, textvariable=self.rcvStr)
		self.label_data.grid(row=2, column=0, columnspan=1)

		self.pckLost = 0
		self.pckLostStr = StringVar()
		self.label_pckLost = Label(self.master, height=1, textvariable=self.pckLostStr)
		self.label_pckLost.grid(row=2, column=1, columnspan=1)

		self.lossRate = 0
		self.lossRateStr = StringVar()
		self.label_loss = Label(self.master, height=1, textvariable=self.lossRateStr)
		self.label_loss.grid(row=2, column=2, columnspan=1)

		self.totalRcvBytes = 0
		self.totalRcvBytesStr = StringVar()
		self.label_totalRcvBytes = Label(self.master, height=1, textvariable=self.totalRcvBytesStr)
		self.label_totalRcvBytes.grid(row=2, column=3, columnspan=1)

		self.totalRcvBytes = 0
		self.dataRate = 0
		self.totalTime = 0
		self.startTime = 0
		self.accumTime = 0
		self.dataRateStr = StringVar()
		self.label_data = Label(self.master, height=1, textvariable=self.dataRateStr)
		self.label_data.grid(row=2, column=4, columnspan=1)

		self.updateText()
	def updateText(self):
			self.rcvStr.set("Recieved packet: " + str(self.rcv))
			self.pckLostStr.set("Packets lost: " + str(self.pckLost))
			self.lossRateStr.set("Loss rate: {:0.2f} %".format(self.lossRate * 100))
			self.totalRcvBytesStr.set("Totol recieved data: " + str(self.totalRcvBytes) + " bytes")
			self.dataRateStr.set("Data rate: {:0.4f} bytes/s".format(self.dataRate))



	def handler(self):
		"""Handler on explicitly closing the GUI window."""
		self.pauseMovie()
		if tkMessageBox.askokcancel("Quit?", "Are you sure you want to quit?"):
			self.tearDown()

		else:  # When the user presses cancel, resume playing.
			self.playMovie()

	def connect(self):
		"Open RSTP socket to the server. This socket then is used to send RTSP request"
		self.rtspSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

		try:
			self.rtspSocket.connect((self.serverAddr, self.serverPort))
		except:
			tkMessageBox.showerror("Failed to connect to server")


	def setupMovie(self):
		"""Setup button handler."""

		if self.state == self.INIT:
			self.sendRtspRequest(self.SETUP)

	def tearDown(self):
		"""Teardown button handler."""

		self.master.destroy()  # Close GUI

		# Delete the cache image from video
		try:
			os.remove(CACHE_FILE_NAME + str(self.sessionID) + CACHE_FILE_EXT)
		except:
			pass

		self.sendRtspRequest(self.TEARDOWN)

	def playMovie(self):
		"""Play button handler."""

		if self.state == self.READY:
			# Create a new thread to listen for RTP packets
			threading.Thread(target=self.listenRtp).start()
			self.playEvent = threading.Event()
			self.playEvent.clear()
			self.sendRtspRequest(self.PLAY)

	def pauseMovie(self):
		"""Pause button handler."""

		if self.state == self.PLAYING:
			self.sendRtspRequest(self.PAUSE)


	def describeReq(self):
		"""Describe button handler."""
		self.sendRtspRequest(self.DESCRIBE)



	def listenRtp(self):
		"Listen for RTP packages"

		while True:
			try:
				data = self.rtpSocket.recv(20480)
				
				if data:
					rtpPacket = RtpPacket()
					rtpPacket.decode(data)
					currFrameNbr = rtpPacket.seqNum() #Server response seq num
					
					print("===================================")
					print("Client Frame Num: " + str(self.frameNbr))
					print("Server Response Frame Num: " + str(currFrameNbr))

					if currFrameNbr > self.frameNbr:  # Discard the late packet
						# Calculate and update Statistics, late packet counted as lost
						self.pckLost += currFrameNbr - self.frameNbr - 1
						self.rcv += 1
						self.lossRate = self.pckLost / (self.pckLost + self.rcv)
						self.totalRcvBytes += sys.getsizeof(rtpPacket.getPayload())
						print("Total rcv {}".format(self.totalRcvBytes))
						print("Payload: {}".format(sys.getsizeof(rtpPacket.getPayload())))
						self.totalTime = int(time()) - self.startTime + self.accumTime
						print("Time {}".format(self.totalTime))
						self.dataRate = (self.totalRcvBytes / self.totalTime) if self.totalTime != 0 else 0

						self.updateText()

						self.frameNbr = currFrameNbr
						self.updateMovie(self.writeFrame(
							rtpPacket.getPayload()))

			except:
				# If paused, stop listening
				if self.playEvent.isSet():
					break
				
				# Close RTP socket
				if self.isTearDowned:
					self.rtpSocket.shutdown(socket.SHUT_RDWR)
					self.rtpSocket.close()
					break

	def sendRtspRequest(self, requestCode):
		"""Send RTSP request to the server."""
		
		"Prepare request to send"
		self.rtspSeq += 1
		if requestCode == self.SETUP and self.state == self.INIT: #Case Set up
			threading.Thread(target=self.recvRtspReply).start()
			request = self.SETUP + " " + self.fileName +  " RTSP/1.0\nCSeq: " + str( self.rtspSeq ) + "\nTransport: RTP/UDP; client_port= " + str(self.rtpPort)
		else:
			self.sentRequest = requestCode
			request = self.requestTemp.format(requestCode, self.fileName, self.rtspSeq, self.sessionID)
		
		
		print(request)
		self.rtspSocket.send(request.encode())

	def recvRtspReply(self):
		"""Receive RTSP request from the server."""
		while True:
			reply = self.rtspSocket.recv(1024)
			print(reply)
			if reply:
				self.ProcessRtspReply(reply)
	           # Close the RTSP socket upon requesting Teardown

			if self.sentRequest == self.TEARDOWN:

				self.rtspSocket.shutdown(socket.SHUT_RDWR)

				self.rtspSocket.close()

				break

			

	def ProcessRtspReply(self, data):
		"""Process the RTSP reply from the server."""
		lines = data.decode().split('\n')
		status = int(lines[0].split()[1])
		seqNum = int(lines[1].split()[1])
		print("===================================")
		print("RTSP from server")
		print(lines)
		
		if (seqNum == self.rtspSeq) and (status == 200):
			# Set up request, when current ID is 0
			print("Processing reply")
			if self.sessionID == 0:
				self.sessionID = int(lines[2].split()[1])
				self.state = self.READY
				print(self.state)
				self.openRtpPort()

			# Process only when the sessionID is matched
			elif self.sessionID == int(lines[2].split()[1]):
				if self.sentRequest == self.TEARDOWN:
					self.state = self.INIT
					# Inform the RTP soket to close
					self.isTearDowned = True

				if self.sentRequest == self.PLAY:
					self.state = self.PLAYING
					self.startTime = int(time())

				if self.sentRequest == self.PAUSE:
					self.state = self.READY
					self.accumTime = self.totalTime
					self.playEvent.set()

				if self.sentRequest == self.DESCRIBE:
					print(data.decode())
	
	def openRtpPort(self):
		"""Open RTP socket binded to a specified port."""

		# Create a new datagram socket to receive RTP packets from the server
		self.rtpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

		# Set the timeout value of the socket to 0.5sec
		self.rtpSocket.settimeout(0.5)

		try:
			# Bind the socket to the address using the RTP port given by the client user
			self.rtpSocket.bind(("", self.rtpPort))

		except:
			tkMessageBox.showerror(
				'Binded FAILED PORT=%d' % self.rtpPort)


	def writeFrame(self, data):
		"""Write the received frame to a temp image file. Return the image file."""

		cachename = CACHE_FILE_NAME + str(self.sessionID) + CACHE_FILE_EXT

		file = open(cachename, "wb")

		file.write(data)

		file.close()

		return cachename

	def updateMovie(self, imageFile):
		"""Update the image file as video frame in the GUI."""
		photo = ImageTk.PhotoImage(PIL.Image.open(imageFile))

		self.label.configure(image=photo, height=288)

		self.label.image = photo
