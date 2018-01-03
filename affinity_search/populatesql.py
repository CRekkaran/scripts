#!/usr/bin/env python

'''Given a results.csv file, put the contents into google sql'''

import sys, re, MySQLdb
import pandas as pd
        
conn = MySQLdb.connect (host = "35.196.158.205",user = "opter",passwd='optimize',db="opt1")
cursor = conn.cursor()

data = pd.read_csv(sys.argv[1])

for (i,row) in data.iterrows():
    insert = 'INSERT INTO params (%s) VALUES (%s)' % (','.join(row.index),','.join(['%s']*len(row)))
    cursor.execute(insert,row)
conn.commit()
