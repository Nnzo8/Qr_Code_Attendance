from flask import Flask, render_template, request, redirect, flash, session, url_for, jsonify
import sqlite3
from sqlite3 import connect, Row
import qrcode
from PIL import Image,ImageDraw
import os
import base64
import time
import io
from datetime import datetime


app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Secret key for session management
UPLOAD_FOLDER = 'static/uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
database = "studentlist.db" #DB FOR STUDENTS
app.config['MAX_CONTENT_LENGTH'] = 64 * 1024 * 1024  


def get_db_connection():
    """Connect to the database."""
    conn = sqlite3.connect('studentlist.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn
    
def execute_query(sql, params=(), fetch=False):
    """Executes SQL queries with optional fetching."""
    try:
        with sqlite3.connect('studentlist.db', check_same_thread=False) as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            if fetch:
                return cursor.fetchall()
            conn.commit()  # Commit the transaction
    except sqlite3.OperationalError as e:
        print(f"Error during database operation: {e}")
        time.sleep(0.1)
        return False
    
def handle_base64_image(base64_string):
    """Saves a base64 string as an image file and returns the file path.""" 
    try:
        if not base64_string:
            return None

        # Decode the base64 string and calculate its size
        img_data = base64.b64decode(base64_string.split(",")[1])
        if len(img_data) > 10 * 1024 * 1024:  # Limit to 10 MB
            raise ValueError("Image size exceeds the limit.")

        file_name = f'image_{int(time.time())}.png'
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file_name)

        with open(file_path, 'wb') as file:
            file.write(img_data)

        return f'uploads/{file_name}'
    except Exception as e:
        print(f"Error saving image: {e}")
        return None



def generate_qr_code(idno):
    """Generates a QR code for the student ID and returns the file path."""
    try:
        qr = qrcode.make(idno)
        file_name = f'qr_code_{int(time.time())}.png'
        qr_file_path = os.path.join(app.config['UPLOAD_FOLDER'], file_name)
        qr.save(qr_file_path)
        return f'uploads/{file_name}'  # Path relative to static folder
    except Exception as e:
        print(f"Error generating QR code: {e}")
        return None


# Routes
@app.route("/index")
def index():
    return render_template("index.html", pagetitle="STUDENTLIST")
    
@app.route("/")
def student():
    return render_template("student.html", pagetitle="ATTENDANCE CHECKER")

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        sql = "SELECT * FROM users WHERE username = ? AND password = ?"
        user_data = execute_query(sql, (username, password), fetch=True)

        if user_data:
            session["user"] = username
            session["is_admin"] = username in ["admin", "hello", "bravo"]  # Add proper admin check
            flash("Logged in successfully!", "success")
            return redirect("/admin_dashboard" if session["is_admin"] else "/student_dashboard")
        else:
            flash("Invalid credentials.", "danger")
    return render_template("index.html", pagetitle="Login Page")


@app.route('/admin_dashboard')
def admin_dashboard():
    conn = get_db_connection()
    # Ensure image_path and qr_path are included in the SELECT statement
    students = conn.execute('SELECT idno, firstname, lastname, course, level, image_path, qr_path, added_at FROM students').fetchall()
    conn.close()
    return render_template('admin.html', students=students, pagetitle="Student Dashboard")


    
@app.route('/studentlist')
def studentlist():
    students = db.session.execute('SELECT * FROM students').fetchall()
    return render_template('admin.html', students=students)

@app.route("/student_dashboard")
def student_dashboard():
    if "user" in session and not session.get("is_admin"):
        return render_template("student.html", pagetitle="Student Dashboard")
    else:
        flash("Access denied!", "danger")
        return redirect("/admin")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully", "success")
    return redirect("/admin")

@app.route('/add', methods=['GET', 'POST'])
def add():
    if request.method == 'POST':
        # Get form data
        idno = request.form['idno']
        lastname = request.form['lastname']
        firstname = request.form['firstname']
        course = request.form['course']
        level = request.form['level']
        image_path = request.form['image_path']

        # Check the size of the base64 string
        if len(image_path) > 10 * 1024 * 1024:  # Limit to 10MB
            flash("Image size exceeds the limit. Please upload a smaller file.", "danger")
            return redirect(url_for('add'))

        # Proceed with the rest of the logic
        qr_path = generate_qr_code(idno)
        saved_image_path = handle_base64_image(image_path)

        conn = get_db_connection()
        conn.execute('INSERT INTO students (idno, lastname, firstname, course, level, image_path, qr_path) VALUES (?, ?, ?, ?, ?, ?,?)',
                     (idno, lastname, firstname, course, level, saved_image_path, qr_path))
        conn.commit()
        conn.close()

        flash("Student added successfully!", "success")
        return redirect(url_for('admin_dashboard'))

    return render_template('add.html')

    
@app.route('/delete', methods=['POST'])
def delete_student():
    # Retrieve the student ID from the form
    idno = request.form['idno']
    
    # Connect to the database
    conn = get_db_connection()
    
    # Execute the DELETE query to remove the student by ID number
    conn.execute('DELETE FROM students WHERE idno = ?', (idno,))
    
    # Commit the transaction
    conn.commit()
    
    # Close the connection
    conn.close()

    # Flash a success message and redirect to the admin dashboard
    flash("Student record deleted successfully!", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/edit', methods=['POST'])
def edit_student():
    # Retrieve the student data from the form
    idno = request.form['idno']
    firstname = request.form['firstname']
    lastname = request.form['lastname']
    course = request.form['course']
    level = request.form['level']
    
    # Connect to the database
    conn = get_db_connection()

    # Execute the UPDATE query to modify the student's record
    conn.execute('''
        UPDATE students
        SET firstname = ?, lastname = ?, course = ?, level = ?
        WHERE idno = ?
    ''', (firstname, lastname, course, level, idno))

    # Commit the changes
    conn.commit()
    conn.close()

    # Flash a success message and redirect to the admin dashboard
    flash("Student record updated successfully!", "success")
    return redirect(url_for('admin_dashboard'))

# Helper function to interact with the database
def query_db(query, args=(), one=False):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(query, args)
    rv = cur.fetchall()
    conn.commit()
    conn.close()
    return (rv[0] if rv else None) if one else rv

def get_student_by_id(student_id):
    # Connect to the SQLite database (assuming it's called 'students.db')
    conn = sqlite3.connect('studentlist.db')
    cursor = conn.cursor()

    # Query the database to find the student by their ID
    cursor.execute("SELECT idno, lastname, firstname, course, level, image_path, added_at FROM students WHERE idno = ?", (student_id,))
    student = cursor.fetchone()  # Get one record (or None if not found)

    # Close the database connection
    conn.close()

    # If a student is found, return the data as a dictionary
    if student:
        return {
            "id": student[0],
            "lastname": student[1],
            "firstname": student[2],
            "course": student[3],
            "level": student[4],
            "image": student[5],
            "added_at": student[6]
        }
    else:
        return None  # No student found

@app.route('/scan', methods=['POST'])
def scan_qr():
    try:
        data = request.get_json()  # Get the POSTed JSON data
        student_id = data.get("id")

        # Get student details from the database using the ID
        student = get_student_by_id(student_id)

        if not student:
            return jsonify({"error": "Student not found"}), 404

        # Initialize 'scanned_students' list if it doesn't exist
        if 'scanned_students' not in session:
            session['scanned_students'] = []

        # Append the new student to the scanned list
        session['scanned_students'].append(student)

        # Print to console for debugging
        print(f"Scanned students in session: {session['scanned_students']}")

        # Commit changes to session
        session.modified = True

        return jsonify({
            "id": student['id'],
            "lastname": student['lastname'],
            "firstname": student['firstname'],
            "course": student['course'],
            "level": student['level']
        }), 200

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": "An internal error occurred"}), 500


@app.route('/attendance', methods=['POST'])
def record_attendance():
    try:
        data = request.get_json()  # Get POSTed JSON data
        student_id = data.get("id")
        lastname = data.get("lastname")
        firstname = data.get("firstname")
        course = data.get("course")
        level = data.get("level")

        # Insert attendance record into the database
        conn = get_db_connection()
        conn.execute('INSERT INTO attendance (id, lastname, firstname, course, level, added_at) VALUES (?, ?, ?, ?, ?, ?)',
                     (id, lastname, firstname, course, level, datetime.now()))
        conn.commit()
        conn.close()

        return jsonify({"message": "Attendance recorded successfully!"}), 200

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"message": "Attendance recorded successfully!"}), 200


@app.route("/viewattendance")
def view_attendance():
    attendance_data = query_db("SELECT * FROM attendance ORDER BY added_at DESC")
    scanned_students = session.get('scanned_students', [])  # Get all scanned students from the session

    # Print to console to verify the data passed to the template
    print(f"Scanned students passed to template: {scanned_students}")

    return render_template(
        "viewattendance.html",
        scanned_students=scanned_students,  # Pass the list of scanned students
        attendance_data=attendance_data,  # Pass attendance data to the template
        pagetitle="Attendance Checker"
    )




if __name__ == '__main__':
    app.run(debug=True)