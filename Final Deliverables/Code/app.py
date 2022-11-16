from flask import Flask, render_template, url_for, request, redirect, flash, abort
from flask_login import LoginManager
from flask_login import login_required, current_user, login_user, logout_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import ibm_db
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
api_key = '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'
sg = SendGridAPIClient(api_key)

# Ibm Db2


def connection():
    try:
        conn = ibm_db.connect(
            "DATABASE=bludb;HOSTNAME=824dfd4d-99de-440d-9991-629c01b3832d.bs2io90l08kqb1od8lcg.databases.appdomain.cloud;\
                PORT=30119;SECURITY=SSL;SSLServerCertificate=DigiCertGlobalRootCA.crt;UID=fpq67161;PWD=3IOG7aiAt5sF2eBq", '', '')
        print("Connected to Database")
        return conn
    except:
        print("Not Connected to Database")


# App
app = Flask(__name__)
app.config['SECRET_KEY'] = '71001910'

conn = connection()

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)


class User(UserMixin):
    def __init__(self, user_json):
        self.user_json = user_json

    def get_id(self):
        object_id = self.user_json.get('PERSONID')
        return str(object_id)


@login_manager.user_loader
def load_user(user_id):
    sql = "SELECT * FROM login WHERE personid=?"
    stmt = ibm_db.prepare(conn, sql)
    ibm_db.bind_param(stmt, 1, user_id)
    ibm_db.execute(stmt)
    account = ibm_db.fetch_assoc(stmt)
    return User(account)


@app.route('/')
def index():
    return render_template('index.html', index='active', success=request.args.get('success'), danger=request.args.get('danger'))


@app.route('/login')
def login():
    return render_template('login.html', login='active', danger=request.args.get('danger'), success=request.args.get('success'))


@app.route('/login', methods=['POST', 'GET'])
def login_rec():
    if request.method == 'POST':

        email = request.form['email']
        password = request.form['password']
        remember = True if request.form.get('remember') else False

        sql = "SELECT * FROM login WHERE email=?"
        stmt = ibm_db.prepare(conn, sql)
        ibm_db.bind_param(stmt, 1, email)
        ibm_db.execute(stmt)
        account = ibm_db.fetch_assoc(stmt)

        if not account:
            return redirect(url_for('login', danger="You do not have an registered account so, please register and login"))
        else:
            if not check_password_hash(account['PASSWORD'], password):
                return redirect(url_for('login', danger="You've entered a wrong password"))
            else:
                userdetails = User(account)
                login_user(userdetails, remember=remember)
                return redirect(url_for('dashboard', success='Login Successfull'))


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index', success="Logout successfull"))


@app.route('/register')
def register():
    return render_template('register.html', register='active', danger=request.args.get('danger'))


@app.route('/register', methods=['POST', 'GET'])
def addrec():
    if request.method == 'POST':

        firstname = request.form['firstname']
        lastname = request.form['lastname']
        email = request.form['email']
        password = request.form['password']
        re_password = request.form['re-password']
        print(firstname)
        sql = "SELECT * FROM login WHERE email=?"
        prep_stmt = ibm_db.prepare(conn, sql)
        ibm_db.bind_param(prep_stmt, 1, email)
        ibm_db.execute(prep_stmt)
        account = ibm_db.fetch_assoc(prep_stmt)

        if account:
            return redirect(url_for('login', danger="You already have an account so, please login with your credentials"))

        elif (password != re_password):
            return redirect(url_for('register', danger="Your password doesn't match"))

        else:
            insert_sql = "INSERT INTO login(firstname,lastname,email,password) VALUES (?,?,?,?)"
            prep = ibm_db.prepare(conn, insert_sql)
            ibm_db.bind_param(prep, 1, firstname)
            ibm_db.bind_param(prep, 2, lastname)
            ibm_db.bind_param(prep, 3, email)
            ibm_db.bind_param(prep, 4, generate_password_hash(
                password, method='sha256'))
            ibm_db.execute(prep)

            message = Mail(
                from_email='admin@pta.com',
                to_emails=email,
                subject='Registration Successfull',
                html_content='<strong>and easy to do anywhere,</strong>')
            res = sg.send(message)
            print(res.status_code)
            print(res.body)
            print(res.headers)
    return redirect(url_for('login', success="Registration Successfull"))


@app.route('/dashboard')
@login_required
def dashboard():

    # Expense Details SQL
    expensedetails = []
    sql = "SELECT AMOUNT,DETAILS,CHAR(DATE(DANDT),USA) AS DATEADDED, CHAR(TIME(DANDT),USA) AS TIMEADDED FROM USERDATA WHERE USERID = ?"
    stmt = ibm_db.prepare(conn, sql)
    ibm_db.bind_param(stmt, 1, current_user.user_json['PERSONID'])
    ibm_db.execute(stmt)
    details = ibm_db.fetch_assoc(stmt)
    while details != False:
        expensedetails.append(details)
        details = ibm_db.fetch_assoc(stmt)

    label = [row['DATEADDED'] for row in expensedetails]
    amountlabel = [row['AMOUNT'] for row in expensedetails]

    # Totalexpense SQL
    sql2 = "SELECT SUM(AMOUNT) AS TOTALVAL FROM USERDATA WHERE USERID = ?"
    stmt2 = ibm_db.prepare(conn, sql2)
    ibm_db.bind_param(stmt2, 1, current_user.user_json['PERSONID'])
    ibm_db.execute(stmt2)
    totalexpense = ibm_db.fetch_assoc(stmt2)
    if totalexpense['TOTALVAL'] is None:
        totalexpense['TOTALVAL'] = 0

    # walletbalance SQL
    sql3 = "SELECT SUM(WALLETAMOUNT) AS TOTALVAL FROM WALLET WHERE WALLETID = ?"
    stmt3 = ibm_db.prepare(conn, sql3)
    ibm_db.bind_param(stmt3, 1, current_user.user_json['PERSONID'])
    ibm_db.execute(stmt3)
    walletbalance = ibm_db.fetch_assoc(stmt3)
    if walletbalance['TOTALVAL'] is None:
        walletbalance['TOTALVAL'] = 0
        availablebalance = 0
    else:
        availablebalance = int(
            walletbalance['TOTALVAL']) - int(totalexpense['TOTALVAL'])
    if (availablebalance <= 50):
        flash("Your balance is too low!!!")
    elif (availablebalance > 50 and availablebalance <= 200):
        flash("Your balance is getting low so take care of your expenses...!!!")

    return render_template('dashboard.html', dashboard='active', name=current_user.user_json['FIRSTNAME'], success=request.args.get('success'), danger=request.args.get('danger'), expensedetails=expensedetails, totalexpense=totalexpense['TOTALVAL'], walletbalance=availablebalance, label=label, amountlabel=amountlabel)


@app.route('/addexpense/<balance>', methods=['POST'])
@login_required
def addexpense(balance):
    amount = request.form['amount']
    detail = request.form['details']

    if (int(amount) == 0):
        return redirect(url_for('dashboard', danger="Please enter some amount"))

    else:
        sql = "INSERT INTO USERDATA(USERID,AMOUNT,DETAILS) VALUES(?,?,?)"
        stmt = ibm_db.prepare(conn, sql)
        ibm_db.bind_param(stmt, 1, current_user.user_json['PERSONID'])
        ibm_db.bind_param(stmt, 2, amount)
        ibm_db.bind_param(stmt, 3, detail)
        ibm_db.execute(stmt)
        print('sendMail')
        if (int(balance) <= 100):
            try:
                message = Mail(
                    from_email='admin@pta.com',
                    to_emails=current_user.user_json['EMAIL'],
                    subject='Low Balance !!',
                    html_content='<strong>and easy to do anywhere,</strong>')
                res = sg.send(message)
                print(res.status_code)

            except:
                print("e")
        return redirect(url_for('dashboard', success="Expense added successfully"))


@app.route('/addmoney', methods=['POST'])
@login_required
def addmoney():
    amount = request.form['walletamount']

    if (int(amount) == 0):
        return redirect(url_for('dashboard', danger="Please enter some amount"))

    else:
        sql = "INSERT INTO WALLET(WALLETID,WALLETAMOUNT) VALUES(?,?)"
        stmt = ibm_db.prepare(conn, sql)
        ibm_db.bind_param(stmt, 1, current_user.user_json['PERSONID'])
        ibm_db.bind_param(stmt, 2, amount)
        ibm_db.execute(stmt)

        return redirect(url_for('dashboard', success="Money added successfully"))


# Delete
@app.route('/deleteexpense/<val>/<amount>')
@login_required
def deleteexpense(val, amount):

    sql = "DELETE USERDATA WHERE USERID=? AND CHAR(TIME(DANDT),USA)= ? AND AMOUNT=?"
    stmt = ibm_db.prepare(conn, sql)
    ibm_db.bind_param(stmt, 1, current_user.user_json['PERSONID'])
    ibm_db.bind_param(stmt, 2, val)
    ibm_db.bind_param(stmt, 3, amount)
    ibm_db.execute(stmt)

    return redirect(url_for('dashboard', success="Deleted Successfully"))


@app.errorhandler(500)
def page_not_found():
    return redirect(url_for('index', danger="oops!!! error occured, try again")), 500


@app.errorhandler(404)
def not_found():
    return redirect(url_for('index', danger="oops!!! error occured, try again")), 404


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
