
# D118-PS-Homerooms

Script to find a student's homeroom teacher name and room number and upload to a SFTP server in order to be imported into PowerSchool via the AutoComm feature. Will export the student number, teacher full name and the room number from the course in the *cc* table.

## Overview

The script first does a query for all students in PowerSchool. It then begins to go through each student one at a time, only processing further for active students.

Then it takes the current date and does a query to find all full year terms from the *terms* table in PowerSchool, and each term's start and end dates are compared to today's date to find the term (or terms) that is currently active for that student.

A third query is run for the student, finding enrollments from the *cc* table for the current term, for K-12 this is filtered to only classes that have "HR" in the course_number. Pre-K students only have one class, so we just take that (though we ignore extra "IREADY" enrollments). The section and teacher ID is retrieved, then two more queries retrieve the teacher's full name and the room number that the course takes place in.

This information is exported to a tab delimited .txt file, which is then uploaded via SFTP for future import on the PowerSchool server.

## Requirements

The following Environment Variables must be set on the machine running the script:

- POWERSCHOOL_READ_USER
- POWERSCHOOL_DB_PASSWORD
- POWERSCHOOL_PROD_DB
- D118_SFTP_USERNAME - *This can be replaced with an environment variable of the username of your specific SFTP server*
- D118_SFTP_PASSWORD - *This can be replaced with an environment variable of the password of your specific SFTP server*
- D118_SFTP_ADDRESS - *This can be replaced with an environment variable of the address of your specific SFTP server*

These are fairly self explanatory, slightly more context is provided in the script comments.

Additionally,the following Python libraries must be installed on the host machine (links to the installation guide):

- [Python-oracledb](https://python-oracledb.readthedocs.io/en/latest/user_guide/installation.html)
- [pysftp](https://pypi.org/project/pysftp/)

**As part of the pysftp connection to the SFTP server, you must include the server host key in a file** with no extension named "known_hosts" in the same directory as the Python script. You can see [here](https://pysftp.readthedocs.io/en/release_0.2.9/cookbook.html#pysftp-cnopts) for details on how it is used, but the easiest way to include this I have found is to create an SSH connection from a Linux machine using the login info and then find the key (the newest entry should be on the bottom) in ~/.ssh/known_hosts and copy and paste that into a new file named "known_hosts" in the script directory.

You will also need a SFTP server running and accessible that is able to have files written to it in the directory /sftp/homerooms/ or you will need to customize the script (see below)
In order to import the information into PowerSchool, a scheduled AutoComm job should be setup, that uses the managed connection to your SFTP server, and imports into student_number, home_room, and a custom field that holds the homeroom number, for us that is U_StudentsUserFields.homeroom_number. The field delimiter is a tab, and the record delimiter is LF with the UTF-8 character set. That setup is a bit out of the scope of this readme.

## Customization

This a very specific and customized script for our use at D118. For customization or use outside of my specific use case at D118, you will probably want to look at and edit the following items outside of the environment variables above:

- If your terms with homerooms are not full years, remove the `WHERE IsYearRec = 1` from the terms query
- If your Pre-K students have homerooms or more than one class, you will want to remove the `if grade < 0:` block and merge it with the query under the `else:`
- If your homerooms do not always contain the letters "HR" in them, you will want to change the `WHERE instr(course_number, 'HR') > 0` to be relevant to the naming scheme in your PowerSchool setup, or remove it and do the filtering in Python directly (though this is slower as you will be processing many more results)
- If there are other courses that contain the letters "HR" in them (we have Choir with CHR as an example), or other courses that the Pre-K students have (IREADY is ours), you will want to change the constant list `IGNORED_CLASS_NUMS` to include those course numbers that should be ignored
- If you want to include different information about the teacher of the homeroom instead of just the full name, change the `SELECT users.lastfirst FROM schoolstaff...` to include any of the fields from the *users* table (email, teachernumber, etc)
- If you want to use a different directory for the SFTP upload, change the `sftp.chdir('/sftp/homerooms/')` line to have your directory path in the quotes. There are some commented debug lines above and below this line that can help with showing which directory you are currently in when you log in and its contents.
