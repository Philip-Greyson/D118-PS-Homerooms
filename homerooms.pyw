"""Script to find a student's homeroom teacher and room number based on their enrolled classes.

https://github.com/Philip-Greyson/D118-PS-Homerooms
Filters to current yearlong term, exports results into .txt file and uploads to SFTP server to be AutoComm'd into PowerSchool

needs oracledb: pip install oracledb --upgrade
needs pysftp: pip install pysftp --upgrade
"""
# importing module
import datetime  # needed to get current date to check what term we are in
import os  # needed to get environment variables
from datetime import *

import oracledb  # needed for connection to PowerSchool (oracle database)
import pysftp  # needed for sftp file upload

un = os.environ.get('POWERSCHOOL_READ_USER')  # username for read-only database user
pw = os.environ.get('POWERSCHOOL_DB_PASSWORD')  # the password for the database account
cs = os.environ.get('POWERSCHOOL_PROD_DB')  # the IP address, port, and database name to connect to

#set up sftp login info
sftpUN = os.environ.get('D118_SFTP_USERNAME')
sftpPW = os.environ.get('D118_SFTP_PASSWORD')
sftpHOST = os.environ.get('D118_SFTP_ADDRESS')
cnopts = pysftp.CnOpts(knownhosts='known_hosts')  # connection options to use the known_hosts file for key validation

print(f"Username: {un} |Password: {pw} |Server: {cs}")  # debug so we can see where oracle is trying to connect to/with
print(f"SFTP Username: {sftpUN} |SFTP Password: {sftpPW} |SFTP Server: {sftpHOST}")  # debug so we can see what credentials are being used
badnames = ['use','test','teststudent','test student','testtt','testt','testtest']

IGNORED_CLASS_NUMS = ["CHR", "IREADY"]  # class numbers that should be ignored

if __name__ == '__main__':  # main file execution
	with oracledb.connect(user=un, password=pw, dsn=cs) as con:  # create the connecton to the database
		with con.cursor() as cur:  # start an entry cursor
			with open('Homeroom_log.txt', 'w') as log:  # open a file for logging
				with open('Homerooms.txt', 'w') as outputfile:  # open the output file
					startTime = datetime.now()
					startTime = startTime.strftime('%H:%M:%S')
					print(f'INFO: Execution started at {startTime}')
					print(f'INFO: Execution started at {startTime}', file=log)
					print("Connection established: " + con.version)
					# print('ID\tHomeroom\tHomeroom Numbers', file=outputfile) # print header line in output file

					try:
						# get all students in PowerSchool
						cur.execute('SELECT student_number, first_name, last_name, id, schoolid, enroll_status, home_room, grade_level, dcid FROM students ORDER BY student_number DESC')
						students = cur.fetchall()  # fetchall() is used to fetch all records from result set and store the data from the query into the rows variable
						today = datetime.now()  # get todays date and store it for finding the correct term later
						# today = today - timedelta(days=1)  # used for testing other dates
						# print("today = " + str(today), file=log) # debug

						for student in students:  # go through each entry in the students result.
							try:
								# print(student) # debug
								if (str(student[1]).lower() not in badnames) and (str(student[2]).lower() not in badnames):  # check first and last name against array of bad names, only print if both come back not in it
									homeroom = ""  # reset back to blank each user until we actually find info for them
									homeroom_number = ""  # reset back to blank each user until we actually find info for them
									idNum = int(student[0])  # what we would refer to as their "ID Number" aka 6 digit number starting with 22xxxx or 21xxxx
									firstName = str(student[1])
									lastName = str(student[2])
									internalID = int(student[3])  # get the internal id of the student that is referenced in the classes entries
									schoolID = str(student[4])
									status = int(student[5])  # active on 0 , inactive 1 or 2, 3 for graduated
									currentHomeroom = str(student[6]) if student[6] else ""
									currentHomeroom_number = ""  # set current homeroom number to blank just for strange edge cases. If they have are active and have one it will be updated later
									grade = int(student[7])
									stuDCID = str(student[8])

									if(status == 0):  # only worry about the students who are active, otherwise wipe out their homeroom as the homeroom and homeroom_number remain blank
										termid = None  # set to None by default until we can find a valid term
										try:
											try:
												# get a list of terms for the school, filtering to only full years
												cur.execute("SELECT id, firstday, lastday, schoolid, dcid FROM terms WHERE IsYearRec = 1 AND schoolid = :schoolid ORDER BY dcid DESC", schoolid=schoolID)  # using bind variables as best practice https://python-oracledb.readthedocs.io/en/latest/user_guide/bind.html#bind
												terms = cur.fetchall()
											except Exception as er:
												print(f'ERROR getting results of term query for {idNum}: {er}')
												print(f'ERROR getting results of term query for {idNum}: {er}', file=log)
											for term in terms:  # go through every term
												termStart = term[1]
												termEnd = term[2]
												if ((termStart - timedelta(days = 21) < today) and (termEnd + timedelta(days = 60) > today)):  # compare todays date to the start and end dates with 3 week leeway before school so it populates before the first day of school. 2 month leeway at the end of the term should cover most of the summer
													termid = str(term[0])
													termDCID = str(term[4])
													# print(f'DBUG: {idNum} has good term for school {schoolID}: {termid} | {termDCID}')
													# print(f'DBUG: {idNum} has good term for school {schoolID}: {termid} | {termDCID}', file=log)
										except Exception as er:
											print(f'ERROR getting term for {idNum} : {er}')
											print(f'ERROR getting term for {idNum} : {er}', file=log)
										if termid:  # check to see if we found a valid term before we continue
											try:  # put the course retrieval in its own try/except block
												if grade < 0:  # if they are a pre-k kid, we just take whatever course they are enrolled in
													cur.execute("SELECT course_number, teacherid, sectionid FROM cc WHERE studentid = :studentid AND termid = :term ORDER BY course_number", studentid=internalID, term=termid)
												else:  # for k-12, we want to search for a HR section
													cur.execute("SELECT course_number, teacherid, sectionid FROM cc WHERE instr(course_number, 'HR') > 0 AND studentid = :studentid AND termid = :term ORDER BY course_number", studentid=internalID, term=termid)  # instr() filters to results that have HR in the course_number column
												courses = cur.fetchall()
												if courses:  # only overwrite the homeroom if there is actually data in the response (skips students with no enrollments)
													for course in courses:
														courseNum = str(course[0])  # course "numbers" are just text
														if courseNum not in IGNORED_CLASS_NUMS:  # check for some extra classes that pre-k students have and classes that have HR in the name to filter them out
															teacherID = str(course[1])  # store the unique id of the teacher
															sectionID = str(course[2])  # store the unique id of the section, used to get classroom number later
															# print(f'DBUG: Found good class for {idNum}: {courseNum} tought by {teacherID}', file=log) # debug
														# else: # debug
															# print(f'DBUG: Found "bad" class for {idNum}: {courseNum}', file=log) # debug
													try:  # put teacher and room info in its own try/except block
														# once we have gotten the section info for the homeroom, need to get the teacher name
														cur.execute("SELECT users.lastfirst FROM schoolstaff LEFT JOIN users ON schoolstaff.users_dcid = users.dcid WHERE schoolstaff.id = :staffid", staffid=teacherID)
														teachers = cur.fetchall()  # there should really only be one row, so don't bother doing a loop and just take the first result
														homeroom = str(teachers[0][0])  # store the lastfirst into homeroom
														# now that we found the homeroom and teacher name, also get the room number
														cur.execute("SELECT room FROM sections WHERE id = :sectionid", sectionid=sectionID)  # get the room number assigned to the sectionid correlating to our home_room
														rooms = cur.fetchall()
														homeroom_number = str(rooms[0][0])

														cur.execute("SELECT homeroom_number FROM u_studentsuserfields WHERE studentsdcid = :studentsdcid", studentsdcid=stuDCID)  # fetch their current homeroom room number for comparison
														oldRoomNumber = cur.fetchall()
														currentHomeroom_number = str(oldRoomNumber[0][0]) if oldRoomNumber[0][0] else ""  # if there is no result/null for their current homeroom room number, just set it to a blank

													except Exception as er:
														print(f'ERROR getting teacher or room number for student {idNum}: {er}')
														print(f'ERROR getting teacher or room number for student {idNum}: {er}',file=log)

													# print main info as a log line so we can go back and look easily
													print(f'INFO: Student ID: {idNum} | Course Number: {courseNum} | Teacher ID: {teacherID} | Section ID: {sectionID} | Teacher Name: {homeroom} | Room Number: {homeroom_number}', file=log)

											except Exception as er:
												print(f'ERROR getting courses for {idNum} : {er}')
												print(f'ERROR getting courses for {idNum} : {er}', file=log)
										else:  # if we did not find a valid term, just print out a warning
											print(f'WARN: Could not find a valid term for todays date of {today}, skipping student {idNum}')
											print(f'WARN: Could not find a valid term for todays date of {today}, skipping student {idNum}', file=log)

									# give some log info if their homeroom changed from what it currently is
									if homeroom != currentHomeroom:
										if currentHomeroom == "":
											print(f'WARN: Student {idNum} was enrolled in a new homeroom when they previously had none - {homeroom}')
											print(f'WARN: Student {idNum} was enrolled in a new homeroom when they previously had none - {homeroom}', file=log)
										else:
											print(f'WARN: Student {idNum}\'s homeroom changed from {currentHomeroom} to {homeroom}')
											print(f'WARN: Student {idNum}\'s homeroom changed from {currentHomeroom} to {homeroom}', file=log)

									if homeroom_number != currentHomeroom_number:
										if currentHomeroom_number == "":
											print(f'WARN: Student {idNum} has a new homeroom number when they previously had none - {homeroom_number}')
											print(f'WARN: Student {idNum} has a new homeroom number when they previously had none - {homeroom_number}', file=log)
										else:
											print(f'WARN: Student {idNum}\'s homeroom number changed from {currentHomeroom_number} to {homeroom_number}')
											print(f'WARN: Student {idNum}\'s homeroom number changed from {currentHomeroom_number} to {homeroom_number}', file=log)

									print(f'{idNum}\t{homeroom}\t{homeroom_number}')
									if (homeroom != currentHomeroom) or (homeroom_number != currentHomeroom_number):  # only output them if something has changed
										print(f'{idNum}\t{homeroom}\t{homeroom_number}',file=outputfile)  # do the actual output to the file, tab delimited

							except Exception as er:
								print(f'ERROR: General student error on {idNum}: {er}')
								print(f'ERROR: General student error on {idNum}: {er}', file=log)


					except Exception as er:
						print(f'ERROR: General program error: {er}')
						print(f'ERROR: General program error: {er}', file=log)

				try:
					# after all the output file is done writing and now closed, open an sftp connection to the server and place the file on there
					with pysftp.Connection(sftpHOST, username=sftpUN, password=sftpPW, cnopts=cnopts) as sftp:
						print('INFO: SFTP connection established')
						print('INFO: SFTP connection established', file=log)
						# print(sftp.pwd)  # debug to show current directory
						# print(sftp.listdir())  # debug to show files and directories in our location
						sftp.chdir('/sftp/homerooms/')
						# print(sftp.pwd) # debug to show current directory
						# print(sftp.listdir())  # debug to show files and directories in our location
						sftp.put('Homerooms.txt')  # upload the file onto the sftp server
						print("INFO: Schedule file placed on remote server")
						print("INFO: Schedule file placed on remote server", file=log)
				except Exception as er:
					print(f'ERROR: SFTP error: {er}')
					print(f'ERROR: SFTP error: {er}', file=log)

				endTime = datetime.now()
				endTime = endTime.strftime('%H:%M:%S')
				print(f'INFO: Execution ended at {endTime}')
				print(f'INFO: Execution ended at {endTime}', file=log)
