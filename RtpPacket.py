import sys
from time import time
HEADER_SIZE = 12

class RtpPacket:	
	header = bytearray(HEADER_SIZE)

	def __init__(self):
		pass
		
	def encode(self, version, padding, extension, cc, seqnum, marker, pt, ssrc, payload):
		timeStamp = int(time())
		header = bytearray(HEADER_SIZE)

		header[0] = (version << 6 | padding << 5 | extension << 4 | cc) # 2bits | 1 bit | 1 bit | 4 bits
		header[1] = (marker << 7 | pt) # 1bit | 7 bits
		header[2] = (seqnum >> 8) # 8 first bits
		header[3] = (seqnum & 0xFF) # 8 right bits 
		header[4] = (timeStamp >> 24) # first of 32 bits
		header[5] =	(timeStamp >> 16) & 0xFF
		header[6] = (timeStamp >> 8) & 0xFF
		header[7] = timeStamp & 0xFF
		header[8] = (ssrc >> 24) & 0xFF # first of 32 bits
		header[9] = (ssrc >> 16) & 0xFF
		header[10] = (ssrc >> 8) & 0xFF
		header[11] = ssrc & 0xFF

		self.header = header
		self.payload = payload

	def getPacket(self):
		"""Return RTP packet."""
		return self.header + self.payload


	def decode(self, byteStream):
		"""Decode the RTP packet."""
		self.header = bytearray(byteStream[:HEADER_SIZE])
		self.payload = byteStream[HEADER_SIZE:]

	def seqNum(self):
		"""Return sequence (frame) number."""
		seqNum = self.header[2] << 8 | self.header[3]
		return int(seqNum)

	def getPayload(self):
		return self.payload
	