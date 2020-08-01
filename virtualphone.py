#!/bin/python3

import os
import sys
import json
import time
import serial
import _thread
import vobject
import icalendar
import recurring_ical_events
import urllib.request
import datetime
import telepot
from telepot.loop import MessageLoop
from enum import Enum
import binascii

import ssl
ssl._create_default_https_context = ssl._create_unverified_context

# pre-configuration variables, automatically retrieved from environmental variables

# basic Telegram information
BOT_OWNERS = [os.environ['virtualphone_botowner']]
BOT_TOKEN = os.environ['virtualphone_bottoken']

# the default country code
DEFAULT_COUNTRYCODE = os.environ['virtualphone_defaultcountrycode']

# the default master phone to use
MASTERPHONE = os.environ['virtualphone_defaultmasterphone']

# the private ICS address of the calendar to use for filters
CALENDAR_URL = os.environ['virtualphone_calendarurl']

# temporary owners variables
TEMPORARYOWNER_PASSWORD = os.environ['virtualphone_temporaryownerpassword']

#############################
### CONFIGURATION - BEGIN ###
#############################

# enable/disable temporary owners
TEMPORARYOWNER_ENABLE = True
# should the system notify wrong passwords to users requesting escalation as temporary owner?
TELEGRAM_MESSAGE_TEMPORARYOWNER_NOTIFIYWRONGPASSWORD = True
# should the system notify wrong password attempts to owners?
TELEGRAM_MESSAGE_TEMPORARYOWNER_NOTIFIYWRONGPASSWORD_TOOWNERS = True

# the default action to take when receiving calls out of the calendar hours: None to ignore (set as busy), string with default forward number otherwise
# out of calendar calls may be: unknown calls (DEFAULT_OUTOFCALENDARCALLS_UNKNOWNCALLS), known callers not in any group (DEFAULT_OUTOFCALENDARCALLS_CALLERNOTINGROUP), known callers in group not configured (DEFAULT_OUTOFCALENDARCALLS_OUTPUTOFREACHABILITYTIMECALLER)
DEFAULT_OUTOFCALENDARCALLS_UNKNOWNCALLS = None
DEFAULT_OUTOFCALENDARCALLS_CALLERNOTINGROUP = MASTERPHONE
DEFAULT_OUTOFCALENDARCALLS_OUTOFREACHABILITYTIMECALLER = None

#############################
#### CONFIGURATION - END ####
#############################

# folder used to store contacts lists
CONTACTS_FOLDER = './contacts/'

# telegram answer messages
TELEGRAM_MESSAGE_BOOT = 'Service is running'
TELEGRAM_MESSAGE_HELP = 'Available commands:\n/help to show this help message\n/getid to get your chat id\n/getowners to get the chat ids of all current owners\n/addtemporaryowner `<password>` to add a third temporary owner to the bot (authentication is done by exchanging a clear text `<password>`)\n/getcontactscount to get the number of registered phone contacts\n/verbose\_on to enable verbose mode\n/verbose\_off to disable verbose mode\n/command `<c>` to send the AT-command `<c>` to the serial port of the modem\n/call `<number>` `[<from>]` to call a number `<number>` (optionally, from `<from>` number)\n/close to interrupt all existing calls\n/sms `<number>` `<text>` to text `<number>` with `<text>`\n/setforward `<number>` to set the default forwarding phone number to `<number>`\n/getforward to get the default forwarding phone number\n/getforwardfromnumber `<number>` to get the forwarding phone number from a given contact number `<number>`\n/search `<contact_name>` to look for a contact and related numbers from a given (even partial) name `<contact_name>`\n\nYou can also send a .vcf file containing a list of contacts to the bot: the name of the file will be the name of the contacts group, as matched from calendar information.'
TELEGRAM_MESSAGE_GETOWNERS = 'Following owners are enabled:\n{OWNERS}'
TELEGRAM_MESSAGE_GETID = 'Your chat id is {ID}'
TELEGRAM_MESSAGE_VERBOSE = 'Verbose mode is {STATUS}'
TELEGRAM_MESSAGE_TEMPORARYOWNER_ADDED = 'Temporary owner \'{OWNER}\' added'
TELEGRAM_MESSAGE_TEMPORARYOWNER_WRONGPASSWORD = 'Your temporary owner password is wrong'
TELEGRAM_MESSAGE_TEMPORARYOWNER_WRONGPASSWORD_FOROWNERS = 'User \'{USER}\' tried to escalate to temporary owner, unsuccessfully'
TELEGRAM_MESSAGE_TEMPORARYOWNER_DISABLED = 'Temporary owners functionality is not enabled'
TELEGRAM_MESSAGE_SEARCH_RESULT = 'Found contacts for given input name \'{QUERY}\' are:\n{CONTACTS}'
TELEGRAM_MESSAGE_SEARCH_NORESULT = 'No contacts are found for given input name \'{QUERY}\''
TELEGRAM_MESSAGE_CALLINCOMING = 'Incoming call from {NUMBER}'
TELEGRAM_MESSAGE_CALLINCOMING_MASTERPHONE = 'Call forwarded to {NUMBER}'
TELEGRAM_MESSAGE_CALL = 'Preparing a call with {NUMBER}'
TELEGRAM_MESSAGE_CALL_MASTERPHONE = 'Calling {NUMBER}'
TELEGRAM_MESSAGE_CALL_CALLINGNUMBER = 'Calling the contact'
TELEGRAM_MESSAGE_CALL_MERGE = 'Call merged'
TELEGRAM_MESSAGE_CALL_ENDED = 'Call closed'
TELEGRAM_MESSAGE_CALLENDED = 'Call with {NUMBER} closed'
TELEGRAM_MESSAGE_CALLNOTACCEPTED = 'Call from {NUMBER} not accepted'
TELEGRAM_MESSAGE_CLOSE = 'Existent calls interrupted'
TELEGRAM_MESSAGE_GETCONTACTSCOUNT = '{COUNT} phone contacts are currently registered'
TELEGRAM_MESSAGE_GETFORWARDFROMNUMBER = 'Forward number for {NUMBER} is {FORWARD}'
TELEGRAM_MESSAGE_GETFORWARD = 'Your default forward number is {NUMBER}'
TELEGRAM_MESSAGE_SETFORWARD = 'Forward is now configured to {NUMBER}'
TELEGRAM_MESSAGE_RECEIVEDSMS = 'Received SMS message from {NUMBER}: {MESSAGE}'
TELEGRAM_MESSAGE_RECEIVEDCONTACTS = 'Loaded {NEWCONTACTSCOUNT} new contacts for the group \'{GROUPNAME}\' ({TOTALCONTACTSCOUNT} contacts registered)'
TELEGRAM_MESSAGE_RECEIVEDCONTACTSERROR = 'An error just occurred'
TELEGRAM_MESSAGE_RECEIVEDCONTACTSFORMATERROR = 'File format is incorrect (only .vcf files are accepted)'
TELEGRAM_MESSAGE_SMSSENT = 'SMS message sent'

# basic configuration for Huawei E173 modems

SERIAL_PORT_CONTROL = '/dev/ttyUSB0'
SERIAL_PORT_VOICE = '/dev/ttyUSB1'
SERIAL_PORT_LOG = '/dev/ttyUSB2'
SERIAL_BAUDRATE = 115200
SERIAL_NEWLINE = '\r\n'

# available states
class States(Enum):
	booting = 1,
	idle = 2,
	incomingcall_received = 3,
	incomingcall_closed = 4,
	incomingcall_calleronhold = 5,
	incomingcall_masterphoneanswered = 6,
	incomingcall_joined = 7,
	incomingcall_rejected = 8,
	incomingcall_forwarding = 9

# commands to send to the modem at boot
SERIAL_BOOTCOMMANDS = ['AT', 'AT+CLIP=1', 'AT+CRC=1', 'AT+CMGF=1', 'AT+CNMI=1,2']

# commands to send to the modem when receiving an incoming call that is not accepted
ANSWER_ACTION_ONRECEPTION_NOTACCEPTED = [
	'AT+CHUP' # set as busy and disconnect
]

# commands to send to the modem when receiving an incoming call
ANSWER_ACTION_ONRECEPTION = [
	'ATA', # answering the call
	'{SLEEP:1}', # sleeping
	#'AT^DDSETEX=2', # enabling audio
	#'{SLEEP:1}', # sleeping
	'AT+CHLD=2', # putting the call on hold
	'{SLEEP:1}', # sleeping
	'ATD{MASTERPHONE};', # calling the phone of the owner
]

# commands to send to the modem when the third party accepted the call
ANSWER_ACTION_ONLASTENDPOINTANSWER = [
	'AT+CHLD=3' # merge the two calls
	# nothing, in case you want to make it go to the answering machine
]

# commands to send to the modem when one of the parties ends the call
ANSWER_ACTION_ONCLOUSURE = [
	'AT+CHUP', # sets as busy and disconnects
	'AT+CHLD=1' # ends all calls
]

# commands to send to the modem when an error occurs during a call
ANSWER_ACTION_ONERROR = ANSWER_ACTION_ONCLOUSURE

# commands to send to the modem when a new call has to be established
NEWCALL_ACTION_ONREQUEST = [
	'AT+CHUP', # sets as busy and disconnects
	'AT+CHLD=1', # ends all calls
	'ATD{MASTERPHONE};', # calling the phone of the owner
	'{SLEEP:5}', # sleeping
	'AT^DDSETEX=2', # enabling audio
	'{SLEEP:5}', # sleeping
	'AT+CHLD=2', # putting the call on hold
	'{SLEEP:2}', # sleeping
	'ATD{CONTACT};' # calling the contact
]

# commands to send to the modem when an error occurs during an established call
ANSWER_ACTION_ONERROR = ANSWER_ACTION_ONCLOUSURE

# commands to send to close existing calls
CLOSE_ACTION = ANSWER_ACTION_ONCLOUSURE

# string used for unknown callers
UNKNOWN_CALLER = 'unknown'

# local variables
VERBOSE = False
CALLFROM = None
CONTACTS_LIST = []
CURRENTSTATE = States.booting

### USEFUL FUNCTIONS ###

# useful function to tell if a string s starts with a string n
def startswith(s, n): return str(s)[:len(n)] == n

# useful function to tell if a string s ends with a string n
def endswith(s, n): return str(s)[-len(n):] == n

# gets full caller information from a given number, using CONTACTS_LIST
def getfullcallerinfo(n):
	if n is None or n == '': return UNKNOWN_CALLER
	d = getcontactdetailsfromnumber(n, True)
	if d is None: return str(n)
	return '\''+str(d.get('name'))+'\' ('+str(n)+')'

# state function that tells if the current state is s
def isinstate(s):
	global CURRENTSTATE
	return CURRENTSTATE == s

# state function that moves to the state s
def movetostate(s):
	global CURRENTSTATE
	CURRENTSTATE = s
	#send_telegram_message("STATE: "+str(s))

### TELEGRAM FUNCTION ###

def send_telegram_message(m, chat_id=None, parse_mode='Markdown'):
	global BOT_OWNERS, bot
	recipients = BOT_OWNERS
	if chat_id != None and not str(chat_id) in BOT_OWNERS: recipients.append(chat_id)
	for b in recipients: bot.sendMessage(b, str(m), parse_mode=parse_mode)

### SERIAL MODEM FUNCTIONS ###

# sends a control message m to the modem
def serial_control_send(m):
	global VERBOSE
	print(m)
	m = str(m)+SERIAL_NEWLINE
	ser_control.write(m.encode())
	if VERBOSE:
		try: send_telegram_message('`'+str(m)+'`', parse_mode='Markdown')
		except: pass

# initiates a call to n, with optional master phone f
def serial_call(n, f=None):
	global MASTERPHONE
	global CALLFROM
	print("Calling phone...")
	CALLFROM = n
	actions = []
	if f is None: f = MASTERPHONE
	for el in NEWCALL_ACTION_ONREQUEST:
		if '{MASTERPHONE}' in str(el): el = str(el).replace('{MASTERPHONE}', str(f))
		if '{CONTACT}' in str(el): el = str(el).replace('{CONTACT}', str(n))
		actions.append(el)
	print(actions)
	return trigger_commands(actions)

# sends an sms message text to to
def serial_sms(to, text):
	print("Sending sms...")
	try:
		time.sleep(0.5)
		#ser_control.write(b'ATZ\r')
		#time.sleep(0.5)
		#ser_control.write(b'AT+CMGF=1\r')
		#time.sleep(0.5)
		ser_control.write(b'AT+CMGS="' + to.encode() + b'"\r')
		time.sleep(0.5)
		ser_control.write(text.encode() + b"\r")
		time.sleep(0.5)
		ser_control.write(bytes([26]))
		time.sleep(0.5)
		return True
	finally:
		#ser_control.close()
		pass
	return False

# triggers a list of commands commands
def trigger_commands(commands, mp=None):
	global VERBOSE
	for c in commands:
		if not (str(c)[0] == '{' and str(c)[-1] == '}'):
			n = '{MASTERPHONE}'
			if n in str(c): c = c.replace(n, mp)
			serial_control_send(c)
			if VERBOSE: send_telegram_message('`'+str(c)+'`', parse_mode='Markdown')
			continue
		if 'SLEEP' in str(c): time.sleep(int(c[c.index(':')+1:-1]))
		#if "CALLVOICE_WELCOME" in str(c): serial_voice_sendwelcome()

### CONTACTS FUNCTIONS ###

# provides a unique way to represent a phone number, sanitizing it
def sanitizenumber(n, countrycode=DEFAULT_COUNTRYCODE):
	try:
		n = str(n)
		n = n.replace(' ', '').replace('-', '')
		if n[:2] == '00': n = '+'+n[2:]
		if n[0] != '+': n = countrycode+n
		return n
	except: pass
	return None

# removes contacts of the group g from CONTACTS_LIST
def contactslistwithoutgroup(g):
	global CONTACTS_LIST
	r = []
	for e in CONTACTS_LIST:
		if e.get('group').lower() != g.lower(): r.append(e)
	return r

# loads the group g in file f to CONTACTS_LIST
def loadgrouptocontacts(f, g):
	global CONTACTS_LIST
	with open(f) as source_file:
		for vcard in vobject.readComponents(source_file):
			name = None
			try:
				name = vcard.fn.value
				tels = []
				for tel in vcard.contents['tel']:
					t = sanitizenumber(tel.value)
					tels.append(t)
				obj = {'group':g,'name':name,'tels':tels}
				CONTACTS_LIST.append(obj)
			except: continue

# retrieves contacts details from a given number
def getcontactdetailsfromnumber(n, onlyfirst=False):
	global CONTACTS_LIST
	n = sanitizenumber(n)
	r = []
	for e in CONTACTS_LIST:
		if n in e.get('tels'):
			x = e
			x['tel'] = n
			if onlyfirst: return x
			r.append(x)
	if onlyfirst: return None
	return r

# retrieves contacts details from a given contact name
def getcontactdetailsfromname(n, onlyfirst=False):
	global CONTACTS_LIST
	r = []
	for e in CONTACTS_LIST:
		if n.lower() in e.get('name').lower():
			if onlyfirst: return e
			r.append(e)
	if onlyfirst: return None
	return r

# gets all contact files
def getcontactsfiles():
	r = []
	l = os.listdir(CONTACTS_FOLDER)
	for e in l:
		n = '.vcf'
		if e[-len(n):].lower() != n.lower(): continue
		r.append({'filename':CONTACTS_FOLDER+e, 'groupname':e[:-len(n)]})
	return r

### CALENDAR FUNCTIONS ###

# gets the master phone number from a given event title (group, or contact name), None if the master phone number is not found for this temporal moment
def getmasterphonenumberfromeventtitle(t):
	now = datetime.datetime.today()
	nowp1 = now + datetime.timedelta(0,60)
	start_date = (now.year, now.month, now.day, now.hour, now.minute)
	end_date = (nowp1.year, nowp1.month, nowp1.day, nowp1.hour, nowp1.minute)
	ical_string = urllib.request.urlopen(CALENDAR_URL).read()
	calendar = icalendar.Calendar.from_ical(ical_string)
	events = []
	# getting possible events not recurring
	events = calendar.walk('vevent')
	for e in events:
		if str(t).lower() != str(e['SUMMARY']).lower(): continue
		if not (e.get('dtstart').dt.replace(tzinfo=None) < now.replace(tzinfo=None) and now.replace(tzinfo=None) < e.get('dtend').dt.replace(tzinfo=None)): continue
		return str(e['LOCATION'])
	# getting possible recurring events
	events = recurring_ical_events.of(calendar).between(start_date, end_date)
	for e in events:
		if str(t).lower() != str(e['SUMMARY']).lower(): continue
		return str(e['LOCATION'])
	return None

def getmasterphonenumberfromnumber(n, masterphone=None):
	# getting contacts detail from caller number, in order to match it with calendar/forward information
	cd = getcontactdetailsfromnumber(n, True)
	mp = None
	g = None
	# trying to get master phone from name (to override group, if possible), with calendar/forward information
	try:
		n = cd.get('name')
		mp = getmasterphonenumberfromeventtitle(n)
	except: pass
	# getting master phone from group and calendar/forward information, if needed
	if mp is None:
		try:
			g = cd.get('group')
			mp = getmasterphonenumberfromeventtitle(g)
		except: pass
	# setting masterphone, if needed
	if masterphone != None and mp is None: mp = masterphone
	# returning result
	return mp

### HANDLERS ###

# handles incoming Telegram control messages
def handle_telegram_message(msg):
	global CONTACTS_LIST
	global MASTERPHONE
	global VERBOSE
	global BOT_OWNERS
	content_type, chat_type, chat_id = telepot.glance(msg)
	# file received (only for vcf contacts)
	try:
		if msg['document'] != None:
			try:
				# non owner messages are ignored
				if not str(chat_id) in BOT_OWNERS: return
				filename = msg['document']['file_name']
				fileid = msg['document']['file_id']
				if not endswith(filename, '.vcf'):
					send_telegram_message(TELEGRAM_MESSAGE_RECEIVEDCONTACTSFORMATERROR, chat_id=chat_id)
					return
				filelocation = str(CONTACTS_FOLDER)+str(filename)
				bot.download_file(fileid, filelocation)
				group = filename[:-len('.vcf')]
				pre_count = len(CONTACTS_LIST)
				CONTACTS_LIST = contactslistwithoutgroup(group)
				loadgrouptocontacts(filelocation, group)
				post_count = len(CONTACTS_LIST)
				diff = post_count - pre_count
				send_telegram_message(TELEGRAM_MESSAGE_RECEIVEDCONTACTS.replace('{NEWCONTACTSCOUNT}', str(diff)).replace('{TOTALCONTACTSCOUNT}', str(post_count)).replace('{GROUPNAME}', group), chat_id=chat_id)
			except: send_telegram_message(TELEGRAM_MESSAGE_RECEIVEDCONTACTSERROR, chat_id=chat_id)
			return
	except: pass
	t = msg.get('text')
	# non commands are ignored
	if len(t) == 0: return
	if t[0] != '/': return
	if t.lower() == '/help': send_telegram_message(TELEGRAM_MESSAGE_HELP, chat_id=chat_id)
	if t.lower() == '/getid': send_telegram_message(TELEGRAM_MESSAGE_GETID.replace('{ID}', str(chat_id)), chat_id=chat_id)
	# temporary owners support
	if startswith(t.lower(), '/addtemporaryowner'):
		# checking if temporary owners is disabled
		if not TEMPORARYOWNER_ENABLE:
			send_telegram_message(TELEGRAM_MESSAGE_TEMPORARYOWNER_DISABLED, chat_id=chat_id)
			send_telegram_message(TELEGRAM_MESSAGE_TEMPORARYOWNER_WRONGPASSWORD_FOROWNERS.replace('{USER}', chat_id=chat_id))
		else:
			# temporary owners is enabled
			p = t[t.index(' ')+1:]
			# checking if user is a temporary owner
			if p == TEMPORARYOWNER_PASSWORD:
				# user is a temporary owner (correct password)
				BOT_OWNERS.append(chat_id)
				send_telegram_message(TELEGRAM_MESSAGE_TEMPORARYOWNER_ADDED.replace('{OWNER}', chat_id=chat_id))
			else:
				# user is not a temporary owner (wrong password)
				if TELEGRAM_MESSAGE_TEMPORARYOWNER_NOTIFIYWRONGPASSWORD: send_telegram_message(TELEGRAM_MESSAGE_TEMPORARYOWNER_WRONGPASSWORD, chat_id=chat_id)
				if TELEGRAM_MESSAGE_TEMPORARYOWNER_NOTIFIYWRONGPASSWORD_TOOWNERS: send_telegram_message(TELEGRAM_MESSAGE_TEMPORARYOWNER_WRONGPASSWORD_FOROWNERS)
	# non owner messages are ignored
	if not str(chat_id) in str(BOT_OWNERS): return
	# other commands
	if startswith(t.lower(), '/getowners'):
		t = ''
		for o in BOT_OWNERS: t += ' - '+str(o)+'\n'
		send_telegram_message(TELEGRAM_MESSAGE_GETOWNERS.replace('{OWNERS}', t), chat_id=chat_id)
	if startswith(t.lower(), '/search'):
		q = t[t.index(' ')+1:]
		r = getcontactdetailsfromname(q)
		t = ''
		for c in r:
			t += ' - *'+str(c.get('name'))+'* (group: '+str(c.get('group'))+')\n'
			for n in c.get('tels'): t += '        '+n+'\n'
		if len(r) > 0: send_telegram_message(TELEGRAM_MESSAGE_SEARCH_RESULT.replace('{QUERY}', q).replace('{CONTACTS}', t), chat_id=chat_id)
		else: send_telegram_message(TELEGRAM_MESSAGE_SEARCH_NORESULT.replace('{QUERY}', q), chat_id=chat_id)
	if startswith(t.lower(), '/getcontactscount'): send_telegram_message(TELEGRAM_MESSAGE_GETCONTACTSCOUNT.replace('{COUNT}', str(len(CONTACTS_LIST))), chat_id=chat_id)
	if startswith(t.lower(), '/command'): serial_control_send(t[t.index(' ')+1:].replace('\n', ''), chat_id=chat_id)
	if startswith(t.lower(), '/getforwardfromnumber'):
		n = t.split(' ')[1]
		f = getmasterphonenumberfromnumber(n, MASTERPHONE)
		send_telegram_message(TELEGRAM_MESSAGE_GETFORWARDFROMNUMBER.replace('{NUMBER}', n).replace('{FORWARD}', f), chat_id=chat_id)
	else:
		if startswith(t.lower(), '/getforward'): send_telegram_message(TELEGRAM_MESSAGE_GETFORWARD.replace('{NUMBER}', MASTERPHONE), chat_id=chat_id)
	if startswith(t.lower(), '/setforward'):
		try:
			MASTERPHONE = t.split(' ')[1]
			send_telegram_message(TELEGRAM_MESSAGE_SETFORWARD.replace('{NUMBER}', MASTERPHONE), chat_id=chat_id)
		except: pass
	if t.lower() == '/verbose_on':
		VERBOSE = True
		send_telegram_message(TELEGRAM_MESSAGE_VERBOSE.replace('{STATUS}', 'enabled'), chat_id=chat_id)
	if t.lower() == '/verbose_off':
		VERBOSE = False
		send_telegram_message(TELEGRAM_MESSAGE_VERBOSE.replace('{STATUS}', 'disabled'), chat_id=chat_id)
	if startswith(t.lower(), '/call'):
		from_number = None
		t_split = t.split(' ')
		if len(t_split) > 2: from_number = t_split[2]
		send_telegram_message(TELEGRAM_MESSAGE_CALL.replace('{NUMBER}', getfullcallerinfo(t_split[1])), chat_id=chat_id)
		send_telegram_message(TELEGRAM_MESSAGE_CALL_MASTERPHONE.replace('{NUMBER}', MASTERPHONE), chat_id=chat_id)
		serial_call(t_split[1], from_number)
	if startswith(t.lower('/close')):
		trigger_commands(CLOSE_ACTION)
		send_telegram_message(TELEGRAM_MESSAGE_CLOSE, chat_id=chat_id)
	if startswith(t.lower(), '/sms'):
		try:
			if serial_sms(t.split(' ')[1], ' '.join(t.split(' ')[2:])):
				send_telegram_message(TELEGRAM_MESSAGE_SMSSENT, chat_id=chat_id)
		except: pass

# handles incoming serial control messages
def handle_serial_message_control():
	global VERBOSE
	while ser_control.readline():
		r = ser_control.readline()
		try: r = r.decode()
		except: pass
		r = str(r)
		if VERBOSE: send_telegram_message('`'+str(r)+'`', parse_mode='Markdown')
		print("Received: "+str(r))

# handles incoming serial log messages
def handle_serial_message_log():
	global CALLFROM
	global VERBOSE
	ser_log = serial.Serial(port=SERIAL_PORT_LOG, baudrate=SERIAL_BAUDRATE, dsrdtr=True, rtscts=True)
	ser_log.close()
	ser_log.open()
	isreceivingacall = False
	skipfstcallfrom = True
	isreceivingansms = False
	sms_info = []
	sms_texts = []
	while True:
		r = ser_log.readline()
		try: r = r.decode()
		except: pass
		if VERBOSE:
			try: send_telegram_message('`'+str(r)+'`', parse_mode='Markdown')
			except: pass
		print("Received (log): "+str(r))
		# incoming call managing: begin
		if startswith(r, "+CRING"): isreceivingacall = True
		if isreceivingacall and startswith(r, "+CLIP"):
			if skipfstcallfrom:
				skipfstcallfrom = False
				continue
			if isinstate(States.incomingcall_forwarding): continue
			CALLFROM = r.split('"')[1]
			# notifying the incoming call
			if not isinstate(States.incomingcall_received): send_telegram_message(TELEGRAM_MESSAGE_CALLINCOMING.replace('{NUMBER}', getfullcallerinfo(CALLFROM)))
			# moving state
			movetostate(States.incomingcall_received)
			# setting the master phone
			mp = MASTERPHONE
			# trying to get master phone from calendar information
			new_mp = getmasterphonenumberfromnumber(CALLFROM)
			# if a master phone is found in calendar, use it
			if new_mp != None: mp = new_mp
			else: # no master phone found in calendar
				shouldnotaccept = False
				if getfullcallerinfo(CALLFROM) == UNKNOWN_CALLER: # DEFAULT_OUTOFCALENDARCALLS_UNKNOWNCALLS
					# managing unknown callers
					if DEFAULT_OUTOFCALENDARCALLS_UNKNOWNCALLS is None: shouldnotaccept = True
					else: mp = DEFAULT_OUTOFCALENDARCALLS_UNKNOWNCALLS
				else:
					if g is None: # DEFAULT_OUTOFCALENDARCALLS_CALLERNOTINGROUP
						# managing callers with known number but not registered in the contacts list
						if DEFAULT_OUTOFCALENDARCALLS_CALLERNOTINGROUP is None: shouldnotaccept = True
						else: mp = DEFAULT_OUTOFCALENDARCALLS_CALLERNOTINGROUP
					else:
						# managing known callers outside of their time slot in the calendar
						if DEFAULT_OUTOFCALENDARCALLS_OUTOFREACHABILITYTIMECALLER is None: shouldnotaccept = True # DEFAULT_OUTOFCALENDARCALLS_OUTOFREACHABILITYTIMECALLER
						else: mp = DEFAULT_OUTOFCALENDARCALLS_OUTOFREACHABILITYTIMECALLER
				if shouldnotaccept:
					trigger_commands(ANSWER_ACTION_ONRECEPTION_NOTACCEPTED)
					send_telegram_message(TELEGRAM_MESSAGE_CALLNOTACCEPTED.replace('{NUMBER}', getfullcallerinfo(CALLFROM)))
					movetostate(States.incomingcall_rejected)
					movetostate(States.idle)
					continue
			movetostate(States.incomingcall_forwarding)
			send_telegram_message(TELEGRAM_MESSAGE_CALLINCOMING_MASTERPHONE.replace('{NUMBER}', str(mp)))
			trigger_commands(ANSWER_ACTION_ONRECEPTION, mp)
		if startswith(r, "^CONN:1") and not isreceivingacall:
			send_telegram_message(TELEGRAM_MESSAGE_CALL_CALLINGNUMBER)
		if startswith(r, "^CONN:2"):
			send_telegram_message(TELEGRAM_MESSAGE_CALL_MERGE)
			trigger_commands(ANSWER_ACTION_ONLASTENDPOINTANSWER)
			movetostate(States.incomingcall_masterphoneanswered)
		if startswith(r, "^CEND"):
			trigger_commands(ANSWER_ACTION_ONCLOUSURE)
			if isreceivingacall and startswith(r, "^CEND"): send_telegram_message(TELEGRAM_MESSAGE_CALLENDED.replace('{NUMBER}', getfullcallerinfo(CALLFROM)))
			else:
				if startswith(r, "^CEND:1"): send_telegram_message(TELEGRAM_MESSAGE_CALL_ENDED)
			movetostate(States.incomingcall_closed)
			isreceivingacall = False
			CALLFROM = None
			skipfstcallfrom = True
		# incoming call managing: end
		# sma managing: begin
		if startswith(r, "+CMT"):
			sms_info.append(r)
			isreceivingansms = True
		if isreceivingansms and len(sms_info) > 0:
				if r != '\r\n' and r != 'OK\r\n' and (not startswith(r, 'AT+CMGL')) and (not startswith(r, '+CMT')): sms_texts.append(r)
				if len(sms_info) == len(sms_texts):
					for i in range(0, len(sms_info)):
						send_from = UNKNOWN_CALLER
						try: send_from = sms_info[i].split('"')[1]
						except: pass
						send_text = sms_texts[i].replace('\r\n', '')
						# trying to decode received text
						try: send_text = binascii.unhexlify(send_text)
						except: pass
						# notifying the owner
						t = TELEGRAM_MESSAGE_RECEIVEDSMS.replace('{NUMBER}', getfullcallerinfo(send_from)).replace('{MESSAGE}', str(send_text))
						send_telegram_message(t)
						# cleaning up
						sms_info = []
						sms_texts = []
						isreceivingansms = False
		# sms managing: end

### MAIN FUNCTION ###

# checking if quick run mode is enabled
qr = False
try:
	if sys.argv[1] == '--quick': qr = True
except: pass

# loading all contacts
if not qr:
	l = getcontactsfiles()
	for e in l: loadgrouptocontacts(e.get('filename'), e.get('groupname'))
	print('Loaded '+str(len(CONTACTS_LIST))+' contacts')

# initializes communication on serial control port
ser_control = serial.Serial(port=SERIAL_PORT_CONTROL, baudrate=SERIAL_BAUDRATE)
ser_control.close()
ser_control.open()
# sends boot commands to the modem
for m in SERIAL_BOOTCOMMANDS: serial_control_send(m)

# initializes the Telegram bot
bot = telepot.Bot(BOT_TOKEN)

# runs the two threads to manage serial ports of the modem
try:
	_thread.start_new_thread(handle_serial_message_control, ())
	_thread.start_new_thread(handle_serial_message_log, ())
except: print ("Error: unable to start thread")

# sends a boot message to the owner through Telegram
send_telegram_message(TELEGRAM_MESSAGE_BOOT)

# moving to the idle state
movetostate(States.idle)

# runs the thread used to handle incoming Telegram messages
MessageLoop(bot, handle_telegram_message).run_as_thread()
print('Listening ...')

# keeps the program running
while 1: time.sleep(10)
