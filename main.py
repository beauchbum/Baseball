from flask import Flask, render_template, make_response, redirect, url_for, request
import sys
import datetime
from datetime import date, datetime, timedelta
import pymysql
import time

app = Flask(__name__, instance_relative_config=True)
app.config.from_pyfile('config.py')
#vendor.add('lib')

def cloud_sql_connect():

    cloud_dbpass = app.config['DBPASS']
    cloud_dbhost = app.config['DBHOST']
    cloud_dbuser = app.config['DBUSER']
    cloud_dbname = app.config['DBNAME']
    CLOUDSQL_PROJECT = app.config['CLOUDSQL_PROJECT']
    CLOUDSQL_INSTANCE = app.config['CLOUDSQL_INSTANCE']

    conn = pymysql.connect(unix_socket='/cloudsql/{}:{}'.format(CLOUDSQL_PROJECT, CLOUDSQL_INSTANCE), user=cloud_dbuser,
                               host=cloud_dbhost, password=cloud_dbpass, db=cloud_dbname)

    return conn


@app.route('/', methods=['GET', 'POST'])
def index():
    args = request.args

    error = None

    teams = ["NULL", "ATL", "BAL", "BOS", "CHC",
             "CWS", 'CIN', 'CLE', 'COL', 'DET',
             'FLA', 'HOU', 'KAN', 'LAA', 'LAD',
             'MIL', 'MIN', 'NYM', 'NYY', 'OAK',
             'PHI', 'PIT', 'SD', 'SF', 'SEA',
             'STL', 'TB', 'TEX', 'TOR', 'WSH']


    conn = cloud_sql_connect()
    cursor = conn.cursor()

    step = timedelta(days=1)


    date1 = datetime.now().strftime("%Y-%m-%d")
    date2 = (datetime.now()+timedelta(days=5)).strftime("%Y-%m-%d")
    #date2 = '2018-09-30'
    start = datetime.strptime(date1, '%Y-%m-%d')
    start-=step
    end = datetime.strptime(date2, '%Y-%m-%d')
    dates_dict = {}
    dates = []
    while start <= end:
        dates.append(str(start.date()))
        dates_dict[str(start.date())] = []
        start += step

    if "date" in args:

        this_date = args['date']
        max_percent = 100
        for d2 in dates_dict[this_date]:
            max_percent -= int(d2["percent"])

        player1 = args['player1_name'] if args['player1_name'] else None
        team1 = None if args['player1_team'] == 'NULL' else args['player1_team']
        player2 = args['player2_name'] if args['player2_name'] else None
        team2 = None if args['player2_team'] == 'NULL' else args['player2_team']

        if not ((player1 and team1) or (player2 and team2)):
            error = "Must fill out a player and team"

        try:
            percent = int(args['percent'])
            if percent < 0 or percent > max_percent:
                error = "Percent must be between 0 and %s" % max_percent
        except:
            error = "Percent must be a number"

        if error is None:
            query = "Insert into future_picks(date, player_1, team_1, player_2, team_2, percent, active) values(%s,%s,%s,%s,%s,%s, 1)"
            param = [this_date, player1, team1, player2, team2, percent]
            cursor.execute(query, param)
            conn.commit()
        else:
            print(error)

    if "exist_pick" in args:
        delete_id = args['exist_pick']
        query = "update future_picks set active=0 where ID=%s"
        param = [delete_id]
        cursor.execute(query, param)
        conn.commit()

    query = "select * from future_picks where active=1"
    cursor.execute(query)
    res = cursor.fetchall()
    print(res)
    for r in res:
        d = {"id":r[-1], "name1":r[1], "team1":r[2], "name2":r[3], "team2":r[4], "percent":str(r[5])}
        try:
            dates_dict[str(r[0])].append(d)
        except:
            pass

    cursor.close(); conn.close()

    if args:
        return redirect(url_for('index'))
    else:
        return render_template('index.html', dates=dates, dates_dict=dates_dict, teams=teams)

@app.route('/stats', methods=['GET', 'POST'])
def stats():

    conn = cloud_sql_connect()
    cursor = conn.cursor()

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