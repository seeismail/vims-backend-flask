from crypt import methods
import datetime
import uuid
from datetime import date, timedelta
from functools import wraps

import jwt
from flask import Flask, Response, jsonify, make_response, render_template, request
from werkzeug.security import check_password_hash, generate_password_hash
from flask_cors import CORS

from DB.db import CarLogs, Registered, User, Vehicle, db
from runner import Runner

app = Flask(__name__)

app.config[
    "SQLALCHEMY_DATABASE_URI"
] = "postgresql://postgres:root@localhost:5432/vims"


app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = "fyp"
CORS(app)


db.init_app(app)
db.create_all()


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        if "token-required" in request.headers:
            token = request.headers["token-required"]

        if not token:
            return jsonify({"message": "Token is missing!"}), 401

        try:
            data = jwt.decode(token, app.config["SECRET_KEY"], "HS256")
            current_user = User.query.filter_by(public_id=data["public_id"]).first()
        except Exception:
            return jsonify({"message": "Token is invalid!"}), 401

        return f(current_user, *args, **kwargs)

    return decorated


@app.route("/auth/decode_token", methods=["GET"])
@token_required
def decode(current_user):
    print(current_user)
    if not current_user.admin:
        return jsonify({"message": "Cannot perform that function!"})

    token = None

    if "token-required" in request.headers:
        token = request.headers["token-required"]

    print(token)
    if not token:
        return jsonify({"message": "Token is missing!"}), 401

    try:
        data = jwt.decode(token, app.config["SECRET_KEY"], "HS256")
        current_user = User.query.filter_by(public_id=data["public_id"]).first()
        user_data = {}
        user_data["public_id"] = current_user.public_id
        user_data["name"] = current_user.name
        user_data["email"] = current_user.email
        user_data["password"] = current_user.password
        user_data["admin"] = current_user.admin
    except Exception:
        return jsonify({"message": "Token is invalid!"}), 401

    return jsonify(user_data)


# @token_required
@app.route("/auth/user", methods=["POST"])
def create_user():

    # if not current_user.admin:
    #     return jsonify({"message": "Cannot perform that function!"}), 400

    data = request.get_json()

    hashed_password = generate_password_hash(data["password"], method="sha256")

    if bool(User.query.filter_by(email=data["email"]).first()):
        return jsonify({"message": "User Email Already Exists"}), 400

    if bool(User.query.filter_by(name=data["name"]).first()):
        return jsonify({"message": "User Name Already Exists"}), 400

    new_user = User(
        public_id=str(uuid.uuid4()),
        name=data["name"],
        email=data["email"],
        password=hashed_password,
        admin=True,
    )
    db.session.add(new_user)
    db.session.commit()

    return jsonify({"message": "New user created!"})


@app.route("/auth/login", methods=["POST"])
def login():
    auth = request.authorization
    print(auth)

    if not auth or not auth.username or not auth.password:
        return make_response(
            "Could not verify",
            401,
            {"WWW-Authenticate": 'Basic realm="Login required!"'},
        ), 400
    user = User.query.filter_by(name=auth.username).first()
    print(user)
    if not user:
        return make_response(
            "Could not verify",
            401,
            {"WWW-Authenticate": 'Basic realm="Login required!"'},
        ), 400

    if check_password_hash(user.password, auth.password):
        token = jwt.encode(
            {
                "public_id": user.public_id,
                "exp": datetime.datetime.utcnow() + datetime.timedelta(minutes=15000),
            },
            app.config["SECRET_KEY"],
        )
        print(token)
        return jsonify(token)

    return make_response(
        "Could not verify", 401, {"WWW-Authenticate": 'Basic realm="Login required!"'}
    )


@app.route("/user", methods=["GET"])
@token_required
def get_all_users(current_user):

    if not current_user.admin:
        return jsonify({"message": "Cannot perform that function!"})

    users = User.query.all()

    output = []

    for user in users:
        user_data = {}
        user_data["public_id"] = user.public_id
        user_data["name"] = user.name
        user_data["email"] = user.email
        user_data["password"] = user.password
        user_data["admin"] = user.admin
        output.append(user_data)

    return jsonify(output)


@app.route("/user/<public_id>", methods=["GET"])
@token_required
def get_one_user(current_user, public_id):

    if not current_user.admin:
        return jsonify({"message": "Cannot perform that function!"})

    user = User.query.filter_by(public_id=public_id).first()

    if not user:
        return jsonify({"message": "No user found!"})

    user_data = {}
    user_data["public_id"] = user.public_id
    user_data["name"] = user.name
    user_data["email"] = user.email
    user_data["password"] = user.password
    user_data["admin"] = user.admin

    return jsonify(user_data)


@app.route("/users/<public_id>", methods=["PUT"])
@token_required
def promote_user(current_user, public_id):

    if not current_user.admin:
        return jsonify({"message": "Cannot perform that function!"})

    user = User.query.filter_by(public_id=public_id).first()

    if not user:
        return jsonify({"message": "No user found!"})

    user.admin = True
    db.session.commit()

    return jsonify({"message": "The user has been promoted!"})


@app.route("/users", methods=["GET"])
def user_search():
    temp = request.args.get("data")
    output = []
    if not temp:
        users = User.query.all()
        for user in users:
            user_data = {}
            user_data["id"] = user.id
            user_data["name"] = user.name
            user_data["email"] = user.email
            user_data["public_id"] = user.public_id
            output.append(user_data)
        return jsonify(output)
    try:
        X = int(temp)
        print(X)
        Users = User.query.filter(User.id == X)
        for user in Users:
            user_data = {}
            user_data["id"] = user.id
            user_data["name"] = user.name
            user_data["email"] = user.email
            user_data["public_id"] = user.public_id
            output.append(user_data)
        assert len(output) > 0

    except Exception:
        X = str(temp)
        print(X)
        Users = User.query.filter(
            User.name.ilike(X) | (User.email.ilike(X)) | (User.public_id.ilike(X))
        )
        for user in Users:
            user_data = {}
            user_data["id"] = user.id
            user_data["name"] = user.name
            user_data["email"] = user.email
            user_data["public_id"] = user.public_id
            output.append(user_data)

    return jsonify(output)


@app.route("/users", methods=["PUT"])
@token_required
def update_user(current_user):

    if not current_user.admin:
        return jsonify({"message": "Cannot perform that function!"}), 400

    token = None

    if "token-required" in request.headers:
        token = request.headers["token-required"]

    if not token:
        return jsonify({"message": "Token is missing!"}), 401

    try:
        decoded_data = jwt.decode(token, app.config["SECRET_KEY"], "HS256")
    except Exception:
        return jsonify({"message": "Token is invalid!"}), 401

    user = User.query.filter_by(public_id=decoded_data["public_id"]).first()

    if not user:
        return jsonify({"message": "No user found!"})

    data = request.get_json()

    if bool(User.query.filter_by(name=data["name"]).first()):
        return jsonify({"message": "User Already Exists"}), 400


    user.name = data["name"]
    # user.password = generate_password_hash(data["password"], method="sha256")
    if bool(User.query.filter_by(email=data["email"]).first()):
        return jsonify({"message": "User Already Exists"}), 400

    
        

    user.email = data["email"]
    db.session.commit()

    return jsonify({"message": "User Updated!"})


@app.route("/users/<public_id>", methods=["DELETE"])
@token_required
def delete_user(current_user, public_id):

    if not current_user.admin:
        return jsonify({"message": "Cannot perform that function!"})

    user = User.query.filter_by(public_id=public_id).first()

    if not user:
        return jsonify({"message": "No user found!"}), 400

    db.session.delete(user)
    db.session.commit()

    return jsonify({"message": "The user has been deleted!"})



@app.route("/vehicles", methods=["POST"])
def add_vehicle():

    data = request.get_json()

    new_vehicle = Vehicle(
        num_plate=data["num_plate"], type=data["type"], suspicious=False
    )
    db.session.add(new_vehicle)
    db.session.commit()

    return jsonify({"message": "Vehcile Added!"})



@app.route("/searchVehicles", methods=["GET"])
def searchVehicles():
    temp = request.args.get("data")
    output = []
    if not temp:
        vehicles = Vehicle.query.all()
        for vehicle in vehicles:
            user_data = {}
            user_data["id"] = vehicle.id
            user_data["num_plate"] = vehicle.num_plate
            user_data["type"] = vehicle.type
            user_data["suspicious"] = vehicle.suspicious
            output.append(user_data)
        return jsonify(output)

    X = str(temp)
    print(X)
    vehicles = Vehicle.query.filter(
    Vehicle.num_plate.ilike(X)
    )
    for vehicle in vehicles:
        user_data = {}
        user_data["id"] = vehicle.id
        user_data["num_plate"] = vehicle.num_plate
        user_data["type"] = vehicle.type
        user_data["suspicious"] = vehicle.suspicious
        output.append(user_data)

    return jsonify(output)



@app.route("/delete_vehicle/<num_plate>", methods=["DELETE"])
def delete_vehicle(num_plate):
    reg_vehicle = Vehicle.query.filter_by(num_plate=num_plate).first()

    if not reg_vehicle:
        return jsonify({"message": "Visitor Not Found...!"}), 400

    db.session.delete(reg_vehicle)
    db.session.commit()

    return jsonify({"message": "The Registered Vehicle has been deleted!"})


@app.route("/updation_vehicle/<num_plate>", methods=["PUT"])
def updated_vehicle(num_plate):

    data = request.get_json()
    print(data)
    vehicle = Vehicle.query.filter_by(num_plate=num_plate).first()

    if vehicle is None:
        return jsonify({"message": "Doesnot Exist!"}), 400

    try:
        vehicle.num_plate = data["num_plate"]
        vehicle.type = data["type"]
    finally:
        db.session.commit()
        return jsonify({"message": "Vehicle Updated!"})   

     

@app.route("/suspiciousVehicles", methods=["POST"])
def addSuspiciousVehicles():

    data = request.get_json()
    reg_vehicle = Vehicle.query.filter_by(num_plate=data["num_plate"]).first()

    if reg_vehicle:
        return jsonify({"message": "Already in Database...!"}), 400
    
    new_vehicle = Vehicle(
        num_plate=data["num_plate"], type=data["type"], suspicious=data["suspicious"]
    )
    db.session.add(new_vehicle)
    db.session.commit()

    return jsonify({"message": "Vehcile Added to Suspicious!"})


@app.route("/add_suspicious_vehicle/<number_plate>", methods=["PUT"])
def addSuspiciousVehcile(number_plate):

    vehicle = Vehicle.query.filter_by(num_plate=number_plate).first()

    if not vehicle:
        return jsonify({"message": "No Vehicle found!"}), 400

    if  vehicle.suspicious==False:  
        vehicle.suspicious = True
        db.session.commit()
        return jsonify({"message": "Vehicle added to suspicious category..."})
    else:
        return jsonify({"message": "Vehicle Already in suspicious category..."}), 400   

@app.route("/remove_suspicious_vehicle/<number_plate>", methods=["PUT"])
def removeSuspiciousVehcile(number_plate):

    vehicle = Vehicle.query.filter_by(num_plate=number_plate).first()

    if not vehicle:
        return jsonify({"message": "No Vehicle found!"}), 400

    if  vehicle.suspicious==True:  
        vehicle.suspicious = False
        db.session.commit()
        return jsonify({"message": "Vehicle removed from suspicious category..."})
    else:
        return jsonify({"message": "Vehicle Already in Non suspicious category..."}), 400   
    

    vehicle.suspicious = False
    db.session.commit()

    return jsonify({"message": "Vehicle Removed From suspicious category..."})    


@app.route("/registration", methods=["POST"])
def registration_visitor():
    data = request.get_json()
    CNIC = Registered.query.filter_by(cnic=data["cnic"]).first()
    NUM_PLATE = Vehicle.query.filter_by(num_plate=data["num_plate"]).first()

    if CNIC:
        return jsonify({"message": "Cnic Already Registered!"}), 400

    if NUM_PLATE:
        return jsonify({"message": "Liscense Plate Already Registered!"}), 400    

    new_reg = Registered(
        name=data["name"],
        cnic=data["cnic"],
        contactno=data["contactno"],
        gender=data["gender"],
        dor=data["dor"],
        doe=data["doe"],
        vehicles=Vehicle(num_plate=data["num_plate"], type=data["type"]),
    )

    db.session.add(new_reg)
    db.session.commit()

    return jsonify({"message": "Sucessfully Added!"})


@app.route("/update_visitor/<regid>", methods=["PUT"])
def update_reg_visitor(regid):

    data = request.get_json()
    print(regid)
    reg_visitor = Registered.query.filter_by(regid=regid).first()
    vehicle_visior = (
    Registered.query.filter_by(regid=regid)
    .join(Vehicle)
    .add_columns(
        Vehicle.num_plate,
        Vehicle.type,
        Vehicle.suspicious
    )).first()
    vehicle = Vehicle.query.filter_by(num_plate=vehicle_visior.num_plate).first()
    if reg_visitor is None:
        return jsonify({"message": "Doesnot Exist!"}), 400

    vehicle_plate = Vehicle.query.filter_by(num_plate=data["num_plate"]).first()
    if vehicle_plate:
        return jsonify({"message": "Number Plate Already Registered!"}), 400

    try:
        reg_visitor.name = data["name"]
        reg_visitor.cnic = data["cnic"]
        reg_visitor.contactno = data["contactno"]
        reg_visitor.gender = data["gender"]
        reg_visitor.dor = data["dor"]
        reg_visitor.doe = data["doe"]
        vehicle.num_plate = data["num_plate"]
        vehicle.type = data["type"]
    finally:
        db.session.commit()
        return jsonify({"message": "User Updated!"})


@app.route("/delete_visitor/<regid>", methods=["DELETE"])
def delete_visitor(regid):
    reg_visitor = Registered.query.filter_by(regid=regid).first()

    if not reg_visitor:
        return jsonify({"message": "Visitor Not Found...!"})

    db.session.delete(reg_visitor)
    db.session.commit()

    return jsonify({"message": "The Registered Visitor has been deleted!"})


@app.route("/registered_visitors", methods=["GET"])
def registered_visitors_search():
    temp = request.args.get("data")
    output = []
    if not temp:
        output = []
        regVisitor = (
            Registered.query.join(Vehicle)
            .add_columns(
                Registered.regid,
                Registered.name,
                Registered.cnic,
                Registered.contactno,
                Registered.gender,
                Registered.dor,
                Registered.doe,
                Registered.vehicle_id,
                Vehicle.num_plate,
                Vehicle.type,
                Vehicle.suspicious
            )
        ).all()
        for reg in regVisitor:
            user_data = {}
            user_data["regid"] = reg.regid
            user_data["cnic"] = reg.cnic
            user_data["name"] = reg.name
            user_data["contactno"] = reg.contactno
            user_data["gender"] = reg.gender
            user_data["dor"] = reg.dor
            user_data["doe"] = reg.doe
            user_data["vehicel_id"] = reg.vehicle_id
            user_data["num_plate"] = reg.num_plate
            user_data["type"] = reg.type
            user_data["suspicious"] = reg.suspicious
            output.append(user_data)
        return jsonify(output)    
        
    try:
        X = int(temp)
        regVisitors = Registered.query.filter(Registered.regid == X).join(Vehicle, Registered.vehicle_id == Vehicle.id)
        regVisitor = (
            Registered.query.filter(Registered.regid == X)
            .join(Vehicle, Registered.vehicle_id == Vehicle.id)
            .add_columns(
                Registered.regid,
                Registered.name,
                Registered.cnic,
                Registered.contactno,
                Registered.gender,
                Registered.dor,
                Registered.doe,
                Registered.vehicle_id,
                Vehicle.num_plate,
                Vehicle.type,
                Vehicle.suspicious
            )
        ).first()

        user_data = {
            "regid": regVisitor.regid,
            "name": regVisitor.name,
            "cnic": regVisitor.cnic,
            "contactno": regVisitor.contactno,
            "gender": regVisitor.gender,
            "dor": regVisitor.dor,
            "doe": regVisitor.doe,
            "vehicel_id": regVisitor.vehicle_id,
            "num_plate": regVisitor.num_plate,
            "type": regVisitor.type,
            "suspicous": regVisitor.suspicous

        }
        output.append(user_data)
        assert len(output) > 0

    except Exception:
        X = str(temp)
        print(X)
        regVisitor = (
            Registered.query.filter(
                Registered.name.ilike(X)
                | (Registered.cnic.ilike(X))
                | (Registered.contactno.ilike(X))
            )
            .join(Vehicle, Registered.vehicle_id == Vehicle.id)
            .add_columns(
                Registered.regid,
                Registered.name,
                Registered.cnic,
                Registered.contactno,
                Registered.gender,
                Registered.dor,
                Registered.doe,
                Registered.vehicle_id,
                Vehicle.num_plate,
                Vehicle.type,
                Vehicle.suspicious
            )
        ).all()

        output = []
        for reg in regVisitor:
            user_data = {}
            user_data["regid"] = reg.regid
            user_data["cnic"] = reg.cnic
            user_data["name"] = reg.name
            user_data["contactno"] = reg.contactno
            user_data["gender"] = reg.gender
            user_data["dor"] = reg.dor
            user_data["doe"] = reg.doe
            user_data["vehicel_id"] = reg.vehicle_id
            user_data["num_plate"] = reg.num_plate
            user_data["type"] = reg.type
            user_data["suspicious"] = reg.suspicious
            output.append(user_data)
        return jsonify(output)



model_state_global = {"cap": None, "is_feed_started": False, "model": None}


@app.route("/video_feed/destroy_webcam",methods=["POST"])
def destroy_web_cam():
    model_state_global["cap"].release()
    model_state_global["is_feed_started"] = False
    return {"destroy": True}


@app.route("/video_feed/start_webcam",methods=["POST"])
def start_web_cam():
    run = Runner(0)
    cap = run.get_cap()
    if cap.isOpened():
        model_state_global["cap"] = cap
        model_state_global["is_feed_started"] = True
        model_state_global["model"] = run

        return {"video read successfully": True, "model initialized successfully": True}
    else:
        return {"ERROR IN VIDEO": 404}


@app.route("/video_feed/process_webcam",methods=["GET"])
def video_process_webcam():
    run = model_state_global["model"]
    return Response(run.gen(), mimetype="multipart/x-mixed-replace; boundary=frame")





@app.route("/dashboard/recentVisits", methods=["GET"])
def get_dashboard_data():
    all_carlogs = (
    CarLogs.query.join(Vehicle, CarLogs.vehicle_id == Vehicle.id, isouter=True)
    .join(Registered, Vehicle.id == Registered.vehicle_id, isouter=True)
    .add_columns(
        CarLogs.vehicle_id,
        CarLogs.license_plate,
        CarLogs.is_registered,
        CarLogs.is_suspicious,
        CarLogs.is_visitor,
        Vehicle.type,
        Registered.name,
        Registered.cnic,
        Registered.gender,
        CarLogs.time,
        ).order_by(CarLogs.id.desc())
    )
    output = []

    for count in range(len(all_carlogs.all())):
        user_data = {}
        user_data["Vehicle ID"] = all_carlogs[count].vehicle_id
        user_data["license_plate"] = all_carlogs[count].license_plate
        user_data["is_Registered"] = all_carlogs[count].is_registered
        user_data["is_Suspicious"] = all_carlogs[count].is_suspicious
        user_data["is_Visitor"] = all_carlogs[count].is_visitor
        user_data["type"] = all_carlogs[count].type
        user_data["name"] = all_carlogs[count].name
        user_data["cnic"] = all_carlogs[count].cnic
        user_data["gender"] = all_carlogs[count].gender
        user_data["time"] = all_carlogs[count].time
        output.append(user_data)
    return jsonify(output)



@app.route("/dashboard/vehicleToday")
def vehicle_today():
    # vehicles_today = CarLogs.query.filter(CarLogs.time >= str(date.today())).count()

    vehicles_today = CarLogs.query.filter(
        (CarLogs.time >= str(date.today() - timedelta(1)))
        & (CarLogs.time <= str(date.today() + timedelta(1)))
    ).count()
    output = {"VehiclesToday": vehicles_today}
    return output    

@app.route("/dashboard/vehicleTotal")
def vehicle_total():
    vehicles_total = CarLogs.query.count()
    output = {
        "VehiclesTotal": vehicles_total
    }
    return output  

@app.route("/dashboard/suspiciousToday")
def suspiciousToday():
    suspicous_today = (
        CarLogs.query.filter(
            (CarLogs.time >= str(date.today() - timedelta(1)))
            & (CarLogs.time <= str(date.today() + timedelta(1)))
        )
        .filter(CarLogs.is_suspicious == True)
        .count()
    )
    output = {"suspicious_today": suspicous_today}
    return output


@app.route("/dashboard/suspiciousTotal")
def suspiciousTotal():
    suspicous_total = CarLogs.query.filter(CarLogs.is_suspicious == True).count()
    output = {
        "suspicous_total": suspicous_total
    }
    return output

@app.route("/barVehicles", methods=["GET"])
def bar_vehicles():
    cars = Vehicle.query.filter_by(type="CAR").all()
    buses = Vehicle.query.filter_by(type="BUS").all()
    bikes = Vehicle.query.filter_by(type="BIKE").all()
    

    return {"car": len(cars), "buses": len(buses), "bike": len(bikes)}


@app.route("/pieVehicles", methods=["GET"])
def pie_vehciles():
    cars = Vehicle.query.filter_by(type="CAR").all()
    buses = Vehicle.query.filter_by(type="BUS").all()
    bikes = Vehicle.query.filter_by(type="BIKE").all()
    print(len(buses))

    # sus_cars = Vehicle.query.filter_by(type="car", suspicious=True).all()
    # sus_buses = Vehicle.query.filter_by(type="bus", suspicious=True).all()
    # sus_bikes = Vehicle.query.filter_by(type="bike", suspicious=True).all()

    return {
        "car": len(cars),
        "buses": len(buses),
        "bikes": len(bikes),
        # "sus_cars": len(sus_cars),
        # "sus_buses": len(sus_buses),
        # "sus_bikes": len(sus_bikes),
        # reg green blue colors list
        "colors": ["#00FF00", "#0000FF", "#FF0000"],
    }


def daterange(start_date, end_date):
    start_date = date(*map(lambda a: int(a), start_date.split("-")))
    end_date = date(*map(lambda a: int(a), end_date.split("-")))

    for n in range(int((end_date - start_date).days)):
        yield start_date + timedelta(n+1)


@app.route("/carCounts/<starting_date>/<ending_date>", methods=["GET"])
def car_count_datediff(starting_date: str, ending_date: str):
    list_dates = []
    car_counts = []
    for curr_date in daterange(starting_date, ending_date):
        date_formatted = curr_date.strftime("%Y-%m-%d")
        list_dates.append(date_formatted)
        # CarLogs.query.filter(CarLogs.time = f'{date_formatted}').count()
        count = CarLogs.query.filter(
        (CarLogs.time >= str(date.today() - timedelta(1)))
        & (CarLogs.time <= str(date.today() + timedelta(1)))).count()
        #count = CarLogs.query.filter(CarLogs.time >= "{}".format(curr_date)).count()
        car_counts.append(count)
        print(car_counts)

    return {"list_dates": list_dates, "car_counts": car_counts}





if __name__ == '__main__':
    print("Hello")
    db.create_all()
    db.session.commit()
    print("Hello")
    app.run(debug=True)