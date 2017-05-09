from flask import Flask, render_template, make_response, redirect, url_for
from google.appengine.api import users
import sys
import datetime
from datetime import date
import MySQLdb

app = Flask(__name__, instance_relative_config=True)
app.config.from_pyfile('config.py')
#vendor.add('lib')
reload(sys)
sys.setdefaultencoding('utf-8')

def cloud_sql_connect():

    cloud_dbpass = app.config['DBPASS']
    cloud_dbhost = app.config['DBHOST']
    cloud_dbuser = app.config['DBUSER']
    cloud_dbname = app.config['DBNAME']
    cloud_dbport = app.config['DBPORT']
    CLOUDSQL_PROJECT = app.config['CLOUDSQL_PROJECT']
    CLOUDSQL_INSTANCE = app.config['CLOUDSQL_INSTANCE']

    conn = MySQLdb.connect(unix_socket='/cloudsql/{}:{}'.format(CLOUDSQL_PROJECT, CLOUDSQL_INSTANCE), user=cloud_dbuser,
                               host=cloud_dbhost, passwd=cloud_dbpass, db=cloud_dbname)

    return conn


@app.route('/', methods=['GET', 'POST'])
def index():

    teams = ["ATL", "BAL", "BOS", "CHC", "CWS", 'CIN', 'CLE', 'COL', 'DET', 'FLA', 'HOU', 'KAN', 'LAA', 'LAD', 'MIL', 'MIN', 'NYM', 'NYY', 'OAK', 'PHI', 'PIT', 'SD', 'SF', 'SEA', 'STL', 'TB', 'TEX', 'TOR', 'WAS']


    conn = cloud_sql_connect()
    cursor = conn.cursor()

    date1 = str(date.today())
    date2 = '2017-10-01'
    start = datetime.datetime.strptime(date1, '%Y-%m-%d')
    end = datetime.datetime.strptime(date2, '%Y-%m-%d')

    step = datetime.timedelta(days=1)
    dates_dict = {}
    dates = []
    while start <= end:
        dates.append(str(start.date()))
        dates_dict[str(start.date())] = []
        start += step


    query = "select * from future_picks"
    cursor.execute(query)
    res = cursor.fetchall()
    for r in res:
        d = {"name1":r[2], "team1":r[3], "name2":r[4], "team2":r[5], "percent":str(r[6])}
        dates_dict[str(r[1])].append(d)




    return render_template('index.html', dates=dates, dates_dict=dates_dict, teams=teams)
