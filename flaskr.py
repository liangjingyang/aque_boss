
# -*- coding: utf-8 -*-

import sqlite3
import MySQLdb 
import os
import commands
import subprocess
from contextlib import closing

from flask import Flask, request, session, g, redirect, url_for, \
	abort, render_template, flash

# configuration
DATABASE = 'sqlite.db'
DEBUG = True
SECRET_KEY = 'development key'
USERNAME = 'admin'
PASSWORD = 'default'
MYSQL_HOST = 'rdsbiazrmbiazrm.mysql.rds.aliyuncs.com'
MYSQL_PORT = 3306
MYSQL_USER = 'croods'
MYSQL_PASSWD = 'croodsmysql'
MYSQL_DATABASE = 'croods_action_log'


app = Flask(__name__)
app.config.from_object(__name__)
app.config.from_envvar('FLASHKEY_SETTINGS', silent=True)

def connect_mysql():
    g.mysql_conn = MySQLdb.connect(
            host=app.config['MYSQL_HOST'], 
            user=app.config['MYSQL_USER'], 
            passwd=app.config['MYSQL_PASSWD'])
    g.mysql_cur = g.mysql_conn.cursor()

def close_mysql():
    mysql_cur = getattr(g, 'mysql_cur', None)
    if mysql_cur is not None:
        mysql_cur.close()
    mysql_conn = getattr(g, 'mysql_conn', None)
    if mysql_conn is not None:
        mysql_conn.close()

def connect_sqlit():
    g.sqlit = sqlite3.connect(app.config['DATABASE'])

def close_sqlit():
    sqlit = getattr(g, 'sqlit', None)
    if sqlit is not None:
        sqlit.close()

def init_db():
    with closing(connect_sqlit()) as db:
	with app.open_resource('schema.sql', mode='r') as f:
	    db.cursor().executescript(f.read())
	db.commit()

@app.before_request
def before_request():
    pass

@app.teardown_request
def teardown_request(exception):
    close_mysql()
    close_sqlit()

#@app.route('/')
#def show_entries():
    #cur = g.db.execute('select title, text from entries order by id desc')
    #entries = [dict(title=row[0], text=row[1]) for row in cur.fetchall()]
    #return render_template('show_entries.html', entries=entries)

@app.route('/')
def nav():
    connect_sqlit()
    cur = g.sqlit.execute('select id, name, url from nav')
    nav = [dict(id=row[0], name=row[1], url=row[2]) for row in cur.fetchall()]
    return render_template('nav.html', nav=nav)

@app.route('/analysis')
def analysis():
    connect_sqlit()
    cur = g.sqlit.execute('select id, name, url, group_id, sort_id from analysis_menu')
    menu = [dict(id=row[0], name=row[1], url=row[2], group_id=row[3], sort_id=row[4]) for row in cur.fetchall()]
    sorted_menu = sorted(menu, key=lambda menu : menu['sort_id'])  
    sorted_menu2 = sorted(sorted_menu, key=lambda sorted_menu : sorted_menu['group_id'])  
    for i in range(len(sorted_menu2)):
        sorted_menu2[i]['tmp_id'] = i
    return render_template('analysis_main.html', analysis_menu=sorted_menu2)

@app.route('/analysis_gold')
def analysis_gold():
    connect_mysql()
    g.mysql_conn.select_db(app.config['MYSQL_DATABASE'])
    g.mysql_cur.execute('select * from log_money_2015_04')
    logs = [dict(
        id=row[0], 
        sec=row[1], 
        player_id=row[2], 
        player_lv=row[3], 
        action=row[4],
        type_id=row[5],
        num=row[6],
        reason=row[7]
        ) 
        for row in g.mysql_cur.fetchall()]
    logs[0:0] = [dict(
        id="id",
        sec="sec",
        player_id="player_id",
        player_lv="player_lv",
        action="action",
        type_id="type_id",
        num="num",
        reason="reason"
        )]
    for i in range(len(logs)):
        logs[i]['tmp_id'] = i
    return render_template('analysis_gold.html', logs=logs)

@app.route('/analysis_diamond')
def analysis_diamond():
    return render_template('analysis_diamond.html')

@app.route('/analysis_item')
def analysis_item():
    return render_template('analysis_item.html')

@app.route('/analysis_lv')
def analysis_lv():
    return render_template('analysis_lv.html')

@app.route('/public', methods=['GET', 'POST'])
def public():
    result = '' 
    if request.method == 'POST':
        if (not request.form['project_name']) or (not request.form['version']) or (not request.form['language']):
            #result = 'Invalid args'
            result = 'fasle'
        elif os.path.exists('/data/public/public-script/public.lock'):
            result = 'false'
        else:
            project_name = request.form['project_name']
            version = request.form['version']
            language = request.form['language']
            args = project_name + ' ' + version + ' ' + language
            result = 'args: ' + args
            result = result + '\nrunning...'
            cmd = 'cd /data/public/public-script && ' + \
                    './android_debug.sh' + \
                    ' ' + \
                    args + \
                    ' > ' + \
                    '/data/public/public-script/android_debug.log' + \
                    ' 2>&1',
            subprocess.Popen(cmd,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                    )
            session['logseek'] = 0
        return result 
    return render_template('public.html', result=result)

@app.route('/public_log')
def public_log():
    result = ''
    publiclog = '/data/public/public-script/android_debug.log'
    if os.path.exists(publiclog):
        seek = session.get('logseek')
        if seek is None:
            result = 'public finish'
        else:
            fp = open(publiclog)
            fp.seek(seek)
            size = os.path.getsize(publiclog) - seek
            if size >= 6:
                result = fp.read(size - 6)
                finishTag = fp.read(6)
                result = result + finishTag
                if finishTag == "DONE!\n":
                    fp.close()
                    session.pop('logseek', None)
            else:
                result = fp.read(size)
                session['logseek'] = fp.tell()
    else:
        result = 'public finish'
    print(result)
    return result

@app.route('/public_cancel')
def public_cancel():
    os.system('/data/public/public-script/treekill.sh `pgrep android_debug`')
    os.system('rm -f /data/public/public-script/public.lock')
    session.pop('logseek', None)
    return 'cancel finish'

@app.route('/add', methods=['POST'])
def add_entry():
    if not session.get('logged_in'):
	abort(401)
    g.db.execute('insert into entries (title, text) values (?, ?)',
	    [request.form['title'], request.form['text']])
    g.db.commit()
    flash('New entry was successfully posted')
    return redirect(url_for('show_entries'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if request.form['username'] != app.config['USERNAME']:
            error = 'Invalid username'
        elif request.form['password'] != app.config['PASSWORD']:
            error = 'Invalid password'
        else:
            session['logged_in'] = True
            flash('You were logged in')
            return redirect(url_for('show_entries'))
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    flash('You were logged out')
    return redirect(url_for('show_entries'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=80)
