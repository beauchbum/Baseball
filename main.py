from flask import Flask, render_template, make_response, redirect, url_for, request
import sys
import datetime
from datetime import date
import MySQLdb
import time

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

    error = None

    teams = ["NULL", "ATL", "BAL", "BOS", "CHC", "CWS", 'CIN', 'CLE', 'COL', 'DET', 'FLA', 'HOU', 'KAN', 'LAA', 'LAD', 'MIL', 'MIN', 'NYM', 'NYY', 'OAK', 'PHI', 'PIT', 'SD', 'SF', 'SEA', 'STL', 'TB', 'TEX', 'TOR', 'WSH']


    conn = cloud_sql_connect()
    cursor = conn.cursor()

    step = datetime.timedelta(days=1)


    date1 = str(time.strftime("%Y-%m-%d"))
    date2 = '2017-10-01'
    start = datetime.datetime.strptime(date1, '%Y-%m-%d')
    start-=step
    start-=step
    end = datetime.datetime.strptime(date2, '%Y-%m-%d')

    dates_dict = {}
    dates = []
    while start <= end:
        dates.append(str(start.date()))
        dates_dict[str(start.date())] = []
        start += step

    if "date" in request.form:

        this_date = request.form['date']
        max_percent = 100
        for d2 in dates_dict[this_date]:
            max_percent -= int(d2["percent"])

        player1 = request.form['player1_name']
        team1 = request.form['player1_team']
        player2 = request.form['player2_name']
        team2 = request.form['player2_team']

        try:
            percent = int(request.form['percent'])
            if percent < 0 or percent > max_percent:
                error = "Percent must be between 0 and %s" % max_percent
        except:
            error = "Percent must be a number"

        if len(player1.strip()) == 0 or len(player2.strip()) == 0:
            error = "Cannot leave fields blank"

        if error is None:
            query = "Insert into future_picks(date, player_1, team_1, player_2, team_2, percent, active) values(%s,%s,%s,%s,%s,%s, 1)"
            param = [this_date, player1, team1, player2, team2, percent]
            cursor.execute(query, param)
            conn.commit()
        else:
            print error

    if "exist_pick" in request.form:
        delete_id = request.form['exist_pick']
        query = "update future_picks set active=0 where id=%s"
        param = [delete_id]
        cursor.execute(query, param)
        conn.commit()

    query = "select * from future_picks where active=1"
    cursor.execute(query)
    res = cursor.fetchall()
    for r in res:
        d = {"id":r[0], "name1":r[2], "team1":r[3], "name2":r[4], "team2":r[5], "percent":str(r[6])}
        try:
            dates_dict[str(r[1])].append(d)
        except:
            pass



    cursor.close(); conn.close()

    if error is None:
        return render_template('index.html', dates=dates, dates_dict=dates_dict, teams=teams)
    else:
        return render_template('index.html', dates=dates, dates_dict=dates_dict, teams=teams)

@app.route('/stats', methods=['GET', 'POST'])
def stats():

    conn = cloud_sql_connect()
    cursor = conn.cursor()
    streaks = []

    query = "select current_streak, count(1) from accounts where active = 1 group by current_streak order by current_streak desc"
    cursor.execute(query)
    res = cursor.fetchall()
    streaks = res

    query = "select count(1) from accounts where active = 1"
    cursor.execute(query)
    res = cursor.fetchall()
    total = res[0][0]

    cursor.close();
    conn.close()
    return render_template("stats.html", streaks = streaks, total = total)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8000)