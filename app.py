from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from pymongo import MongoClient
import uuid
from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from pymongo import MongoClient
from docx import Document  # Import python-docx
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from docx.shared import Pt
import os
import matplotlib.pyplot as plt
from io import BytesIO
from werkzeug.security import generate_password_hash, check_password_hash


app = Flask(__name__)
app.secret_key = "your_secret_key"

# MongoDB connection
# Get the MongoDB URI from an environment variable
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")  # Use localhost as fallback for testing
client = MongoClient(MONGO_URI)

db = client["feedback_form_db"]
forms_collection = db["forms"]
feedback_collection = db["feedback"]
users_collection = db["users"]

# Ensure default admin and HOD accounts exist
if not users_collection.find_one({"username": "principal"}):
    users_collection.insert_one({
        "username": "principal",
        "password": generate_password_hash("principal123"),
        "role": "admin"
    })

if not users_collection.find_one({"username": "hod"}):
    users_collection.insert_one({
        "username": "hod",
        "password": generate_password_hash("hod123"),
        "role": "hod"
    })

# Default route
@app.route('/')
def home():
    if 'role' in session:
        if session['role'] == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif session['role'] == 'hod':
            return redirect(url_for('hod_dashboard'))
    return redirect(url_for('login'))

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = users_collection.find_one({"username": username})

        if user and check_password_hash(user['password'], password):
            session['user_id'] = str(user['_id'])
            session['username'] = user['username']
            session['role'] = user['role']
            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user['role'] == 'hod':
                return redirect(url_for('hod_dashboard'))
        else:
            flash("Invalid username or password", "danger")

    return render_template('login.html')

# Logout route
@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully", "success")
    return redirect(url_for('login'))

# Admin dashboard (accessible by Principal)
@app.route('/admin_dashboard')
def admin_dashboard():
    if 'role' not in session or session['role'] != 'admin':
        flash("Unauthorized access", "danger")
        return redirect(url_for('login'))

    academic_year = request.args.get('academicYear')
    department = request.args.get('department')
    semester = request.args.get('semester')
    batch = request.args.get('batch')
    page = int(request.args.get('page', 1))
    per_page = 10

    query = {}
    if academic_year:
        query['academic_year'] = {"$regex": academic_year, "$options": "i"}
    if department:
        query['department'] = {"$regex": department, "$options": "i"}
    if semester:
        query['semester'] = semester
    if batch:
        query['batch'] = {"$regex": batch, "$options": "i"}

    forms = list(forms_collection.find(query).skip((page - 1) * per_page).limit(per_page))
    total_forms = forms_collection.count_documents(query)
    total_pages = (total_forms + per_page - 1) // per_page
# Add the academic year based on semester
    for form in forms:
        semester = int(form.get("semester", 0))  # Ensure semester is an integer
        if semester in [1, 2]:
            form["year"] = "First Year"
        elif semester in [3, 4]:
            form["year"] = "Second Year"
        elif semester in [5, 6]:
            form["year"] = "Third Year"
        elif semester in [7, 8]:
            form["year"] = "Fourth Year"
        else:
            form["year"] = "Unknown Year"
    return render_template(
        'admin_dashboard.html',
        str=str,
        forms=forms,
        total_pages=total_pages,
        current_page=page,
        total_forms=total_forms
    )

# HOD dashboard
@app.route('/hod_dashboard')
def hod_dashboard():
    if 'role' not in session or session['role'] != 'hod':
        flash("Unauthorized access", "danger")
        return redirect(url_for('login'))

    # Extract filters from query parameters
    academic_year = request.args.get('academicYear', '').strip()
    department = request.args.get('department', '').strip()
    semester = request.args.get('semester', '').strip()
    batch = request.args.get('batch', '').strip()

    # Build dynamic query based on provided filters
    query = {}
    if academic_year:
        query['academic_year'] = {"$regex": f"^{academic_year}", "$options": "i"}
    if department:
        query['department'] = {"$regex": department, "$options": "i"}
    if semester:
        query['semester'] = semester  # Exact match for semester
    if batch:
        query['batch'] = {"$regex": batch, "$options": "i"}

    # Fetch forms based on the query
    forms = list(forms_collection.find(query))

    # Render the dashboard with all forms and the applied filters
    return render_template(
        'hod_dashboard.html',
        forms=forms,
        str=str,
        filters={
            'academicYear': academic_year,
            'department': department,
            'semester': semester,
            'batch': batch
        }
    )


@app.route('/create_form', methods=['GET', 'POST'])
def create_form():
    if 'role' not in session or session['role'] not in ['hod', 'admin']:
        flash("Unauthorized access", "danger")
        return redirect(url_for('login'))

    if request.method == 'POST':
        academic_year = request.form['academicYear']
        department = request.form['department']
        semester = request.form['semester']
        batch = request.form['batch']

        courses = []
        course_count = int(request.form['courseCount'])
        for i in range(1, course_count + 1):
            course_code = request.form[f'courseCode{i}']
            course_title = request.form[f'courseTitle{i}']
            staff_name = request.form[f'staffName{i}']
            courses.append({
                'course_code': course_code,
                'course_name': course_title,
                'staff_name': staff_name,
            })

        form_id = str(uuid.uuid4())

        try:
            forms_collection.insert_one({
                '_id': form_id,
                'academic_year': academic_year,
                'department': department,
                'semester': semester,
                'batch': batch,
                'courses': courses,
            })
            flash("Form created successfully!", "success")
        except Exception as e:
            flash(f"Error creating form: {str(e)}", "danger")

        # Redirect to the appropriate dashboard
        if session['role'] == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif session['role'] == 'hod':
            return redirect(url_for('hod_dashboard'))

    return render_template('create_form.html')

# Feedback Form (accessible by anyone with the form link)
@app.route('/feedback_form/<form_id>', methods=['GET', 'POST'])
def feedback_form(form_id):
    form_details = forms_collection.find_one({"_id": form_id})
    if not form_details:
        flash("Feedback form not found.", "danger")
        return "Form not found", 404

    semester = int(form_details.get("semester", 1))
    semester_type = "Odd Semester" if semester % 2 != 0 else "Even Semester"

    return render_template(
        'feedback_form.html',
        form_details=form_details,
        semester_type=semester_type
    )

# Submit Feedback
@app.route('/submit_feedback', methods=['POST'])
def submit_feedback():
    try:
        form_id = request.form.get('form_id')
        if not form_id:
            flash("Form ID is missing!", "danger")
            # Redirect back to the form with an error message
            return redirect(request.referrer or url_for('home'))

        form_details = forms_collection.find_one({"_id": form_id})
        if not form_details:
            flash("Feedback form not found.", "danger")
            # Redirect back to the form with an error message
            return redirect(request.referrer or url_for('home'))

        feedback_data = []
        for course in form_details["courses"]:
            course_code = course["course_code"]
            course_feedback = {
                "course_code": course_code,
                "feedback": {}
            }
            for i in range(1, 9):
                question_key = f"q{i}_{course_code}"
                course_feedback["feedback"][f"q{i}"] = request.form.get(question_key)
            course_feedback["suggestions"] = request.form.get(f"suggestions_{course_code}")
            feedback_data.append(course_feedback)

        feedback_document = {
            "form_id": form_id,
            "feedback_data": feedback_data,
        }
        feedback_collection.insert_one(feedback_document)

        # Redirect to the "Thank You" page
        return redirect(url_for('thank_you', form_id=form_id))
    except Exception as e:
        # Log the exception for debugging
        print(f"Error submitting feedback: {e}")

        # Display a friendly error message and redirect back to the form
        flash("An error occurred while submitting your feedback. Please try again.", "danger")
        return redirect(request.referrer or url_for('home'))

    try:
        form_id = request.form.get('form_id')
        if not form_id:
            flash("Form ID is missing!", "danger")
            return redirect(url_for('home'))

        form_details = forms_collection.find_one({"_id": form_id})
        if not form_details:
            flash("Feedback form not found.", "danger")
            return "Form not found", 404

        feedback_data = []
        for course in form_details["courses"]:
            course_code = course["course_code"]
            course_feedback = {
                "course_code": course_code,
                "feedback": {}
            }
            for i in range(1, 9):
                question_key = f"q{i}_{course_code}"
                course_feedback["feedback"][f"q{i}"] = request.form.get(question_key)
            course_feedback["suggestions"] = request.form.get(f"suggestions_{course_code}")
            feedback_data.append(course_feedback)

        feedback_document = {
            "form_id": form_id,
            "feedback_data": feedback_data,
        }
        feedback_collection.insert_one(feedback_document)

        # Redirect to the "Thank You" page with form_id
        return redirect(url_for('thank_you', form_id=form_id))
    except Exception as e:
        flash(f"Error submitting feedback: {str(e)}", "danger")
        return redirect(url_for('home'))

@app.route('/thank_you/<form_id>')
def thank_you(form_id):
    return render_template('thank_you.html', form_id=form_id)


@app.route('/view_report/<form_id>')
def view_report(form_id):
    if 'role' not in session or session['role'] != 'admin':
        flash("Unauthorized access", "danger")
        return redirect(url_for('login'))

    form_details = forms_collection.find_one({"_id": form_id})
    if not form_details:
        return "Form not found", 404

    header_image = url_for('static', filename='images/header.jpg')

    semester = int(form_details.get("semester", 1))
    semester_type = "Odd Semester" if semester % 2 != 0 else "Even Semester"

    feedback_data = list(feedback_collection.find({"form_id": form_id}))

    student_count = len(feedback_data)
    students_participated = len([f for f in feedback_data if f.get("feedback_data")])

    course_averages = {}
    faculty_reports = []
    for course in form_details["courses"]:
        course_code = course["course_code"]
        course_title = course["course_name"]
        staff_name = course["staff_name"]

        ratings = []
        question_means = {f"q{i}": [] for i in range(1, 9)}
        suggestions = []

        for feedback in feedback_data:
            for data in feedback.get("feedback_data", []):
                if data["course_code"] == course_code:
                    ratings.extend(
                        int(data["feedback"].get(f"q{i}", 0)) for i in range(1, 9)
                    )
                    for i in range(1, 9):
                        question_means[f"q{i}"].append(int(data["feedback"].get(f"q{i}", 0)))
                    if data.get("suggestions"):
                        suggestions.append(data["suggestions"])

        course_averages[course_code] = round(sum(ratings) / len(ratings), 2) if ratings else 0

        question_means_avg = [
            (i + 1, round(sum(values) / len(values), 2) if values else 0)
            for i, values in enumerate(question_means.values())
        ]

        faculty_reports.append({
            "course_code": course_code,
            "course_title": course_title,
            "staff_name": staff_name,
            "question_means": question_means_avg,
            "suggestions": suggestions,
        })

    return render_template(
        'report.html',
        header_image=header_image,
        form_details=form_details,
        student_count=student_count,
        students_participated=students_participated,
        course_averages=course_averages,
        faculty_reports=faculty_reports,
        semester_type=semester_type
    )

@app.route('/edit_form/<form_id>', methods=['GET', 'POST'])
def edit_form(form_id):
    # Ensure only authorized users (HOD or Admin) can edit
    if 'role' not in session or session['role'] not in ['hod', 'admin']:
        flash("Unauthorized access", "danger")
        return redirect(url_for('login'))

    # Fetch the existing form from the database
    form = forms_collection.find_one({"_id": form_id})
    if not form:
        flash("Form not found.", "danger")
        return redirect(url_for('admin_dashboard' if session['role'] == 'admin' else 'hod_dashboard'))

    if request.method == 'POST':
        # Get updated form data from the request
        academic_year = request.form['academicYear']
        department = request.form['department']
        semester = int(request.form['semester'])
        batch = request.form['batch']

        # Prepare the courses list
        courses = []
        course_count = int(request.form['courseCount'])
        for i in range(1, course_count + 1):
            course_code = request.form.get(f'courseCode{i}')
            course_title = request.form.get(f'courseTitle{i}')
            staff_name = request.form.get(f'staffName{i}')
            courses.append({
                'course_code': course_code,
                'course_name': course_title,
                'staff_name': staff_name,
            })

        # Update the form in the database
        try:
            forms_collection.update_one(
                {"_id": form_id},
                {
                    "$set": {
                        "academic_year": academic_year,
                        "department": department,
                        "semester": semester,
                        "batch": batch,
                        "courses": courses,
                    }
                }
            )
            flash("Form updated successfully!", "success")
        except Exception as e:
            flash(f"Error updating form: {str(e)}", "danger")

        # Redirect to the appropriate dashboard
        if session['role'] == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif session['role'] == 'hod':
            return redirect(url_for('hod_dashboard'))

    # Render the edit form page with the existing data
    return render_template('create_form.html', form=form, is_edit=True)

@app.route('/delete_form/<form_id>', methods=['POST'])
def delete_form(form_id):
    """
    Deletes a feedback form and all associated feedback from the database.
    Accessible by both HOD and Admin.
    """
    if 'role' not in session or session['role'] not in ['hod', 'admin']:
        flash("Unauthorized access", "danger")
        return redirect(url_for('login'))

    try:
        # Delete the form from the forms collection
        result_form = forms_collection.delete_one({"_id": form_id})

        # Delete all related feedback from the feedback collection
        result_feedback = feedback_collection.delete_many({"form_id": form_id})

        # Check if the form existed and was deleted
        if result_form.deleted_count > 0:
            flash("Form and associated feedback deleted successfully!", "success")
        else:
            flash("Form not found. No deletion occurred.", "danger")
    except Exception as e:
        flash(f"Error deleting form: {str(e)}", "danger")

    # Redirect to the appropriate dashboard based on the role
    if session['role'] == 'admin':
        return redirect(url_for('admin_dashboard'))
    elif session['role'] == 'hod':
        return redirect(url_for('hod_dashboard'))


@app.route('/download_report/<form_id>')
def download_report(form_id):
    """Generate a Word document for the report."""
    form_details = forms_collection.find_one({"_id": form_id})
    if not form_details:
        flash("Form not found.", "danger")
        return redirect(url_for('admin_dashboard'))

    semester = int(form_details.get("semester", 1))
    semester_type = "Odd Semester" if semester % 2 != 0 else "Even Semester"

    feedback_data = list(feedback_collection.find({"form_id": form_id}))
    student_count = len(feedback_data)
    students_participated = len([f for f in feedback_data if f.get("feedback_data")])

    course_averages = {}
    faculty_reports = []
    for course in form_details["courses"]:
        course_code = course["course_code"]
        course_title = course["course_name"]
        staff_name = course["staff_name"]

        ratings = []
        question_means = {f"q{i}": [] for i in range(1, 9)}
        suggestions = []

        for feedback in feedback_data:
            for data in feedback.get("feedback_data", []):
                if data["course_code"] == course_code:
                    ratings.extend(
                        int(data["feedback"].get(f"q{i}", 0)) for i in range(1, 9)
                    )
                    for i in range(1, 9):
                        question_means[f"q{i}"].append(int(data["feedback"].get(f"q{i}", 0)))
                    if data.get("suggestions"):
                        suggestions.append(data["suggestions"])

        course_averages[course_code] = round(sum(ratings) / len(ratings), 2) if ratings else 0

        question_means_avg = [
            (i + 1, round(sum(values) / len(values), 2) if values else 0)
            for i, values in enumerate(question_means.values())
        ]

        faculty_reports.append({
            "course_code": course_code,
            "course_title": course_title,
            "staff_name": staff_name,
            "question_means": question_means_avg,
            "suggestions": suggestions,
        })

    # Helper function to set font style
    def apply_font_style(paragraph, font_name="Bookman Old Style", font_size=12, bold=False):
        for run in paragraph.runs:
            run.font.name = font_name
            run.font.size = Pt(font_size)
            run.bold = bold

    # Generate Word Document
    document = Document()

    # Add header image
    section = document.sections[0]
    header = section.header
    header_paragraph = header.paragraphs[0]
    header_run = header_paragraph.add_run()
    header_run.add_picture("static/images/header.jpg", width=Pt(450))  # Adjust width as needed

    # Add report title
    title_paragraph = document.add_paragraph()
    title_paragraph.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
    run = title_paragraph.add_run("FACULTY PERFORMANCE – STUDENT’S FEEDBACK\nSUMMARY REPORT\n")
    apply_font_style(title_paragraph, font_size=12, bold=True)
    title_paragraph.add_run(f"Academic Year {form_details['academic_year']} ({semester_type})\n").bold = True
    apply_font_style(title_paragraph, font_size=12,bold=True)
    # Add details in table format
    table = document.add_table(rows=4, cols=2)
    table.style = "Table Grid"

    details = [
        ("Department", form_details['department']),
        ("Year and Semester", form_details['batch']),
        ("Students strength", str(student_count)),
        ("Number of students participated in the feedback collection", str(students_participated))
    ]

    for row, (key, value) in enumerate(details):
        cells = table.rows[row].cells
        cells[0].text = key
        cells[1].text = value
        for cell in cells:
            for paragraph in cell.paragraphs:
                apply_font_style(paragraph)

    document.add_paragraph("\n")  # Add some spacing

    # Overall Feedback Report Table
    table = document.add_table(rows=1, cols=3)
    table.style = "Table Grid"
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = "Course Code & Title"
    hdr_cells[1].text = "Subject Handling Faculty"
    hdr_cells[2].text = "Average Point"

    # Make the header text bold
    for cell in hdr_cells:
        for paragraph in cell.paragraphs:
            apply_font_style(paragraph, bold=True)
    for course in form_details["courses"]:
        row_cells = table.add_row().cells
        row_cells[0].text = f"{course['course_code']} - {course['course_name']}"
        row_cells[1].text = course['staff_name']
        row_cells[2].text = f"{course_averages[course['course_code']]:.2f}"
        for cell in row_cells:
            for paragraph in cell.paragraphs:
                apply_font_style(paragraph)

        # Generate chart dynamically
    courses = [f"{course['course_code']} - {course['course_name']}" for course in form_details["courses"]]
    averages = [course_averages[course['course_code']] for course in form_details["courses"]]

    plt.figure(figsize=(10, 6))
    plt.bar(courses, averages, color='skyblue')
    plt.xlabel("Courses", fontsize=12)
    plt.ylabel("Average Points", fontsize=12)
    plt.title("Course Performance Chart", fontsize=14)
    plt.xticks(rotation=45, ha='right')

    # Save chart to a BytesIO buffer
    chart_buffer = BytesIO()
    plt.tight_layout()
    plt.savefig(chart_buffer, format='png')
    plt.close()
    chart_buffer.seek(0)

    # Insert chart into Word document
    document.add_paragraph("\n")  # Add some spacing
    document.add_picture(chart_buffer, width=Pt(450))  # Adjust width as needed
    chart_buffer.close()

    document.add_page_break()

    # Individual Faculty Reports
    particulars = [
        "Explicitly spells out the learning objectives of the course, various chapters, and evaluation pattern",
        "Coverage and completion of the syllabus",
        "Course material / class notes given",
        "Gives assignment / homework regularly and monitors them properly",
        "Is punctual to the class and engages for the entire hour",
        "Presents subject matter on the board / PPTs, etc., neatly in a format readable by all",
        "Provides feedback about the progress of the students and motivates them by giving tips and advice",
        "Encourages the students to actively participate in the class activities (through discussions, question answers, brainstorming, etc.)"
    ]

    for faculty in faculty_reports:
        document.add_heading("Individual Faculty Report", level=2)
        document.add_paragraph(f"Name of the Faculty: {faculty['staff_name']}")
        document.add_paragraph(f"Designation / Department: {form_details['department']}")
        document.add_paragraph(f"Course Code & Title: {faculty['course_code']} - {faculty['course_title']}")
        document.add_paragraph(f"Class & Semester: {form_details['batch']}")

        table = document.add_table(rows=1, cols=3)
        table.style = "Table Grid"
        hdr_cells = table.rows[0].cells
        hdr_cells[0].text = "S.No."
        hdr_cells[1].text = "Particulars"
        hdr_cells[2].text = "Individual Mean"

        for index, mean in faculty["question_means"]:
            row_cells = table.add_row().cells
            row_cells[0].text = str(index)
            row_cells[1].text = particulars[index - 1]
            row_cells[2].text = f"{mean:.2f}"
            for cell in row_cells:
                for paragraph in cell.paragraphs:
                    apply_font_style(paragraph)

        document.add_paragraph("Suggestions:")
        for suggestion in faculty["suggestions"]:
            suggestion_paragraph = document.add_paragraph(f"- {suggestion}")
            apply_font_style(suggestion_paragraph)

        document.add_page_break()

    # Save the document
    file_path = f"feedback_report_{form_id}.docx"
    document.save(file_path)

    return send_file(file_path, as_attachment=True, download_name="Feedback_Report.docx")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
