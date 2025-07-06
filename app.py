
from flask import Flask, render_template, request, redirect, url_for, jsonify
import oracledb
import threading
from datetime import timedelta

app = Flask(__name__)

def get_db_connection():
    dsn = oracledb.makedsn("pam.zong.com.pk", port=6105, sid="query2")
    connection = oracledb.connect(
        user="READONLY",
        password="readonly_123",
        dsn=dsn
    )
    return connection

def fetch_file_data(days=15):
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        # Fetch the relevant data from the DWH_LOG table for the specified number of days
        cursor.execute(f"""
            SELECT LOG, Result, Status, Start_date, End_date
            FROM dwh.dwh_log@crpt WHERE End_date >= SYSDATE - {days}
        """)

        rows = cursor.fetchall()

        file_data = {}
        for row in rows:
            filename = row[0]
            file_detail = {
                "result": row[1],
                "status": row[2],
                "start_date": row[3],
                "end_date": row[4]
            }

            if filename in file_data:
                file_data[filename].append(file_detail)
            else:
                file_data[filename] = [file_detail]

        return file_data

    except oracledb.Error as e:
        print("Error occurred while fetching data from the database:", e)
        return {}

    finally:
        if connection:
            connection.close()

def format_duration(seconds):
    delta = timedelta(seconds=seconds)
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{days}d:{hours}h:{minutes}m:{seconds}s"

def process_file_details(details):
    # Process the details data to calculate duration and update result/status displays
    for detail in details:
        start_date = detail.get('start_date')
        end_date = detail.get('end_date')
        if start_date and end_date:
            duration_seconds = (end_date - start_date).total_seconds()
            detail['duration_formatted'] = format_duration(duration_seconds)
        else:
            detail['duration_formatted'] = "0d:0h:0m:0s"

        detail['result_display'] = 'Proceeded' if detail.get('result') == 'Y' else 'Pending'
        detail['status_display'] = 'Completed' if detail.get('status') == 0 else 'Pending'

    return sorted(details, key=lambda x: x['duration_formatted'], reverse=True)

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if username == 'username' and password == 'password':
            return jsonify(success=True)
        else:
            return jsonify(success=False, error='Invalid credentials, please try again.')

    return render_template('login1.html')

@app.route('/home')
def home():
    data = {}

    def fetch_data():
        nonlocal data
        data = fetch_file_data()  # Fetch default 15 days of data

    fetch_thread = threading.Thread(target=fetch_data)
    fetch_thread.start()
    fetch_thread.join()

    return render_template('home.html', data=data)

@app.route('/file_details/<filename>')
def file_details(filename):
    data = {}

    def fetch_data():
        nonlocal data
        data = fetch_file_data()  # Default to fetching 5 days of data

    fetch_thread = threading.Thread(target=fetch_data)
    fetch_thread.start()
    fetch_thread.join()

    details = data.get(filename, [])

    if not details:
        return render_template('file_detail.html', file_name=filename, data=[], total_count=0)

    # Process details in a separate thread
    process_thread = threading.Thread(target=process_file_details, args=(details,))
    process_thread.start()
    process_thread.join()

    total_count = len(details)
    num_files_to_show = int(request.args.get('num_files', 5))
    top_files = details[:num_files_to_show]

    return render_template(
        'file_detail.html',
        file_name=filename,
        data=details,
        total_count=total_count,
        top_files=top_files
    )

@app.route('/fetch_trend_data/<filename>')
def fetch_trend_data(filename):
    days = int(request.args.get('days', 5))  # Get number of days from the user, default to 5
    data = {}

    def fetch_data():
        nonlocal data
        data = fetch_file_data(days=days)

    fetch_thread = threading.Thread(target=fetch_data)
    fetch_thread.start()
    fetch_thread.join()

    details = data.get(filename, [])

    if not details:
        return jsonify([])

    # Process details in a separate thread
    process_thread = threading.Thread(target=process_file_details, args=(details,))
    process_thread.start()
    process_thread.join()

    return jsonify(details)

if __name__ == '__main__':
    app.run(debug=True, port=5055)
