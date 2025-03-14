from flask_cors import CORS
from flask import Flask, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from pymongo import MongoClient
import math
from bson import json_util  # เพิ่ม import นี้ที่บรรทัดบน
import json

app = Flask(__name__)

# กำหนด CORS
CORS(app, resources={r"/*": {"origins": "*"}})

# เชื่อมต่อกับ MongoDB
client = MongoClient("mongodb+srv://s6506022420011:0949700912INET@users.ttwq4.mongodb.net/")  # ใช้ MongoDB URI ของคุณ
db = client["users"]  # แทนที่ด้วยชื่อฐานข้อมูลของคุณ
users_collection = db["users"]  # นักเรียน
teacher_staff_collection = db["TeacherStaff"]  # อาจารย์และเจ้าหน้าที่

# ฟังก์ชันเข้าสู่ระบบ
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")
    
    # ค้นหาผู้ใช้จากฐานข้อมูล
    user = users_collection.find_one({"username": username}) or teacher_staff_collection.find_one({"username": username})

    if not user:
        return jsonify({"message": "User not found"}), 404
    
    # กรณีที่ผู้ใช้ล็อกอินครั้งแรก (รหัสผ่านยังเป็น plain text)
    if user.get("first_login", False):  # ตรวจสอบว่าเป็นครั้งแรกที่เข้าสู่ระบบ
        if user["password"] == password:
            hashed_password = generate_password_hash(password)

            # ตรวจสอบว่าเป็นนักเรียนหรืออาจารย์/เจ้าหน้าที่
            if user["role"] == "student":
                collection_to_update = users_collection  # สำหรับนักเรียน
            else:
                collection_to_update = teacher_staff_collection  # สำหรับอาจารย์หรือเจ้าหน้าที่

            collection_to_update.update_one(
                {"username": username},
                {"$set": {"password": hashed_password, "first_login": False}}
            )

            return jsonify({
                "message": "Login successful, please change your password",
                "role": user["role"],
                "first_login": True
            }), 200
        else:
            return jsonify({"message": "Invalid username or password"}), 401
    
    # กรณีเข้าสู่ระบบครั้งถัดไป ตรวจสอบ hashed password
    if user.get("first_login", False) is False:  # ถ้าไม่ใช่การล็อกอินครั้งแรก
        if not check_password_hash(user["password"], password):  # ตรวจสอบรหัสผ่านที่แฮช
            return jsonify({"message": "Invalid username or password"}), 401

    # ตรวจสอบบทบาทของผู้ใช้เพื่อกำหนดหน้าถัดไป
    if user["role"] == "student":
        return jsonify({
            "message": "Login successful, redirecting to student profile",
            "role": "student",
            "first_login": False,
            "profile": user["profile"]
        }), 200
    else:
        return jsonify({
            "message": "Login successful, redirecting to staff/teacher profile",
            "role": user["role"],
            "first_login": False,
            "profile": user["profile"]
        }), 200

# ฟังก์ชันเปลี่ยนรหัสผ่าน
@app.route('/change-password', methods=['POST'])
def change_password():
    data = request.json
    username = data.get("username")
    new_password = data.get("new_password")

    print(f"Received change password request for user: {username}")  # Debug log

    # ค้นหาผู้ใช้จากฐานข้อมูล
    user = users_collection.find_one({"username": username}) or teacher_staff_collection.find_one({"username": username})
    
    if not user:
        return jsonify({"message": "User not found"}), 404

    # อัปเดตรหัสผ่านในฐานข้อมูล
    hashed_password = generate_password_hash(new_password)
    
    # ตรวจสอบว่าเป็นนักเรียนหรืออาจารย์/เจ้าหน้าที่
    collection_to_update = users_collection if user["role"] == "student" else teacher_staff_collection

    collection_to_update.update_one(
        {"username": username},
        {"$set": {"password": hashed_password, "first_login": False}}
    )

    return jsonify({"message": "Password changed successfully"}), 200

@app.route('/students-Table', methods=['GET'])
def get_students():
    students = []
    for user in users_collection.find({"role": "student"}, {"_id": 0, "profile": 1}):
        profile = user.get("profile", {})
        students.append({
            "student_id": profile.get("student_id"),
            "name": profile.get("name"),
            "program": profile.get("program"),
            "phone": profile.get("phone"),
            "status": "",  # ปล่อยว่างไว้
            "company": ""  # ปล่อยว่างไว้
        })
    return jsonify(students)

# ฟังก์ชันดึงข้อมูลโปรไฟล์นักศึกษา
@app.route('/student-profile', methods=['GET'])
def get_student_profile():
    username = request.args.get("username")
    
    if not username:
        return jsonify({"message": "Username is required"}), 400  # แจ้งข้อผิดพลาดหากไม่มี username
    
    # ค้นหาข้อมูลผู้ใช้จากฐานข้อมูล
    user = users_collection.find_one({"username": username})
    if not user:
        return jsonify({"message": "User not found"}), 404
    
    profile = user.get("profile", {})
    return jsonify({"profile": profile})


# ฟังก์ชันอัปเดตข้อมูลโปรไฟล์ (ยกเว้นรหัสผ่าน)
@app.route('/update-profile', methods=['POST'])
def update_profile():
    data = request.json
    username = data.get("username")
    updated_profile = data.get("profile")

    user = users_collection.find_one({"username": username})
    
    if not user:
        return jsonify({"message": "User not found"}), 404

    # อัปเดตโปรไฟล์ (ไม่รวมรหัสผ่าน)
    users_collection.update_one(
        {"username": username},
        {"$set": {"profile": updated_profile}}  # อัปเดตข้อมูลโปรไฟล์
    )

    return jsonify({"message": "Profile updated successfully"}), 200

@app.route('/upload-students', methods=['POST'])
def upload_students():
    students = request.json  # รับข้อมูล JSON
    if not students:
        return jsonify({"error": "No data provided"}), 400

    for student in students:
        # ตรวจสอบว่ามี username นี้ใน database หรือยัง
        existing_user = users_collection.find_one({"username": student["username"]})
        if existing_user:
            continue  # ข้ามถ้าข้อมูลซ้ำ

        # บันทึกข้อมูลใหม่ลง MongoDB
        users_collection.insert_one(student)

    return jsonify({"message": "Students uploaded successfully!"}), 200

db = client["indus"]
companies_collection = db["indus"]

# ฟังก์ชันดึงข้อมูลบริษัททั้งหมด
@app.route('/companies', methods=['GET'])
def get_companies():
    companies = []
    for company in companies_collection.find({}, {"_id": 0}):  # ไม่ให้ดึง _id
        print("Company from DB:", company)  # Add this line
        companies.append(company)
    return jsonify(companies), 200

# ฟังก์ชันเพิ่มข้อมูลบริษัทใหม่
import random

# ปรับปรุงฟังก์ชันเพิ่มบริษัทให้มีฟิลด์จำนวนนักศึกษา
@app.route('/add-company', methods=['POST'])
def add_company():
    data = request.get_json(force=True)
    print(data['company'])
    # สร้าง company_id แบบสุ่ม 9 หลัก
    company_id = str(random.randint(100000000, 999999999))

    new_company = {
        "company_id": company_id,  # เพิ่ม company_id
        "student_count": 0,  # เพิ่มฟิลด์นับจำนวนนักศึกษา เริ่มต้นที่ 0
        "company": {  # ข้อมูลบริษัทจะถูกเก็บภายใต้คีย์ "company"
            "company_name": data['company']['company_name'],
            "address": data['company']['address'],
            "location":  data['company']['location'],
            "contact_person":  data['company']['contact_person'],
            "contact_phone": data['company']['contact_phone'],
            "job_position":  data['company']['job_position'],
            "internship_available":  data['company']['internship_available'],
            "job_description":  data['company']['job_description'],
            "qualifications":  data['company']['qualifications'],
        }
    }

    # เพิ่มข้อมูลบริษัทใหม่ลงใน MongoDB
    result = companies_collection.insert_one(new_company)
    return jsonify({"message": "Company added successfully!", "company_id": company_id}), 201

# ฟังก์ชันแก้ไขข้อมูลบริษัท
@app.route('/edit-company/<company_id>', methods=['PUT'])
def edit_company(company_id):
    data = request.json  # รับข้อมูล JSON ที่ส่งมา
    updated_company = data.get("company")  # ข้อมูลที่อัปเดต

    # ค้นหาบริษัทจาก company_id
    company = companies_collection.find_one({"company_id": company_id})

    if not company:
        return jsonify({"message": "Company not found"}), 404

    # อัปเดตข้อมูล
    companies_collection.update_one(
        {"company_id": company_id},
        {"$set": {"company": updated_company}}
    )

    return jsonify({"message": "Company updated successfully!"}), 200

@app.route('/add-skills-to-company/<company_id>', methods=['POST'])
def add_skills_to_company(company_id):
    try:
        data = request.json
        skills = data.get('skills')

        if not skills:
            return jsonify({"error": "ต้องระบุทักษะ"}), 400

        company = companies_collection.find_one({"company_id": company_id})
        if not company:
            return jsonify({"error": "ไม่พบบริษัท"}), 404

        # ตรวจสอบว่ามีคุณสมบัติ (qualifications) อยู่แล้วหรือไม่
        existing_qualifications = company['company'].get('qualifications', '')
        
        # อัพเดทคุณสมบัติของบริษัท
        updated_qualifications = existing_qualifications
        if existing_qualifications:
            updated_qualifications += ", "
        updated_qualifications += ", ".join([skill.get('skill', {}).get('skill_name', '') for skill in skills])
        
        companies_collection.update_one(
            {"company_id": company_id},
            {"$set": {"company.qualifications": updated_qualifications.strip()}}
        )

        return jsonify({"message": "เพิ่มทักษะให้บริษัทเรียบร้อยแล้ว"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
    # เพิ่ม endpoint ใหม่สำหรับลบทักษะออกจากบริษัท
@app.route('/remove-skill-from-company/<company_id>', methods=['DELETE'])
def remove_skill_from_company(company_id):
    try:
        data = request.json
        skill_name = data.get('skill_name')

        if not skill_name:
            return jsonify({"error": "ต้องระบุชื่อทักษะที่ต้องการลบ"}), 400

        # ค้นหาบริษัท
        company = companies_collection.find_one({"company_id": company_id})
        if not company:
            return jsonify({"error": "ไม่พบบริษัท"}), 404

        # ตรวจสอบว่ามีทักษะที่ต้องการลบหรือไม่
        current_qualifications = company['company'].get('qualifications', '')
        if not current_qualifications:
            return jsonify({"error": "บริษัทไม่มีทักษะที่บันทึกไว้"}), 404

        # แยกทักษะเป็น list และลบทักษะที่ต้องการ
        skills_list = [skill.strip() for skill in current_qualifications.split(',')]
        if skill_name not in skills_list:
            return jsonify({"error": "ไม่พบทักษะที่ต้องการลบในรายการ"}), 404

        # ลบทักษะออกและรวม list กลับเป็น string
        skills_list.remove(skill_name)
        updated_qualifications = ', '.join(skills_list) if skills_list else ''

        # อัพเดทข้อมูลในฐานข้อมูล
        companies_collection.update_one(
            {"company_id": company_id},
            {"$set": {"company.qualifications": updated_qualifications}}
        )

        return jsonify({"message": "ลบทักษะเรียบร้อยแล้ว"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
###################################################################################################################################################

# เพิ่มต่อจากส่วนเชื่อมต่อ MongoDB collections อื่นๆ
db_skill = client["Skills"]  # database ชื่อ skill
skill_collection = db_skill["Skills"]  # collection ชื่อ skill

# ฟังก์ชันดึงข้อมูลทักษะทั้งหมด
@app.route('/skills', methods=['GET'])
def get_skills():
    try:
        skills = []
        # แก้ไขการ query โดยไม่เอา _id
        cursor = skill_collection.find({}, {"_id": 0})
        for skill in cursor:
            skills.append(skill)
        print("Retrieved skills:", skills)
        return jsonify(skills)
    except Exception as e:
        print("Error getting skills:", str(e))
        return jsonify({"error": str(e)}), 500

@app.route('/add-skill', methods=['POST'])
def add_skill():
    try:
        data = request.json
        print("Received data:", data)
        
        skill_name = data.get("skill_name")
        if not skill_name:
            return jsonify({"error": "Skill name is required"}), 400

        # ตรวจสอบว่ามีทักษะนี้อยู่แล้วหรือไม่
        existing_skill = skill_collection.find_one(
            {"skill.skill_name": skill_name},
            {"_id": 0}  # ไม่เอา _id
        )
        if existing_skill:
            return jsonify({"error": "Skill already exists"}), 409

        skill_id = str(random.randint(100000000, 999999999))
        
        new_skill = {
            "skill_id": skill_id,
            "skill": {
                "skill_name": skill_name
            }
        }
        
        result = skill_collection.insert_one(new_skill)
        # ส่งกลับข้อมูลโดยไม่รวม _id
        return jsonify({
            "skill_id": skill_id,
            "skill": {
                "skill_name": skill_name
            }
        }), 201
        
    except Exception as e:
        print("Error type:", type(e))
        print("Error details:", str(e))
        return jsonify({"error": f"Failed to add skill: {str(e)}"}), 500

# ฟังก์ชันอัพเดททักษะของผู้ใช้
@app.route('/update-user-skills', methods=['POST'])
def update_user_skills():
    try:
        data = request.json
        print("Received update data:", data)  # Debug log
        
        username = data.get("username")
        new_skills = data.get("skills")
        
        if not username or new_skills is None:
            return jsonify({"error": "Username and skills are required"}), 400

        result = users_collection.update_one(
            {"username": username},
            {"$set": {"profile.skills": new_skills}}
        )
        
        if result.modified_count == 0:
            return jsonify({"error": "User not found or skills not modified"}), 404
            
        print(f"Updated skills for user {username}")  # Debug log
        return jsonify({"message": "Skills updated successfully"}), 200
        
    except Exception as e:
        print("Error updating user skills:", str(e))  # Debug log
        return jsonify({"error": str(e)}), 500
    
##############################################################################################################################

# เพิ่ม collection ใหม่
db_match = client["match"]
match_collection = db_match["match"]

@app.route('/match-company', methods=['POST'])
def match_company():
    try:
        data = request.json
        student_id = data.get('student_id')
        company_id = data.get('company_id')

        if not student_id or not company_id:
            return jsonify({"message": "กรุณาระบุข้อมูลให้ครบถ้วน"}), 400

        # ตรวจสอบว่ามีการจับคู่อยู่แล้วหรือไม่
        existing_match = match_collection.find_one({
            "macth.student_id": student_id
        })

        # ถ้าพบข้อมูลการจับคู่
        if existing_match:
            matched_company = existing_match["macth"]["company_id"]
            return jsonify({
                "message": f"คุณได้เลือกสถานประกอบการรหัส {matched_company} ไปแล้ว ไม่สามารถเลือกเพิ่มได้"
            }), 400

        # ถ้าไม่พบการจับคู่ สร้างการจับคู่ใหม่
        match_id = str(random.randint(1000000000, 9999999999))
        new_match = {
            "macth_id": match_id,
            "macth": {
                "student_id": student_id,
                "company_id": company_id,
                "status": "กำลังดำเนินการ"
            }
        }

        # บันทึกข้อมูลลงฐานข้อมูล
        match_collection.insert_one(new_match)

        # เพิ่มจำนวนนักศึกษาที่ฝึกงานในบริษัทนั้น
        companies_collection.update_one(
            {"company_id": company_id},
            {"$inc": {"student_count": 1}},  # เพิ่มค่า student_count ขึ้น 1
            upsert=False
        )

        return jsonify({
            "message": "จับคู่สถานประกอบการเรียบร้อยแล้ว",
            "match_id": match_id
        }), 201

    except Exception as e:
        return jsonify({"message": f"เกิดข้อผิดพลาด: {str(e)}"}), 500

@app.route('/check-match-status/<student_id>', methods=['GET'])
def check_match_status(student_id):
    try:
        # ค้นหาข้อมูลการจับคู่
        match = match_collection.find_one({
            "macth.student_id": student_id
        })
        
        if match:
            # หาข้อมูลบริษัทที่จับคู่
            company = companies_collection.find_one({
                "company_id": match["macth"]["company_id"]
            })
            
            company_name = company["company"]["company_name"] if company else "ไม่พบข้อมูลบริษัท"
            
            return jsonify({
                "has_match": True,
                "status": match["macth"]["status"],
                "company_id": match["macth"]["company_id"],
                "company_name": company_name
            })
        
        return jsonify({
            "has_match": False,
            "status": None,
            "company_id": None,
            "company_name": None
        })

    except Exception as e:
        return jsonify({"message": f"เกิดข้อผิดพลาด: {str(e)}"}), 500
    
@app.route('/all-matches', methods=['GET'])
def get_all_matches():
    try:
        matches = []
        for match in match_collection.find({}, {"_id": 0}):
            matches.append(match)
        return jsonify(matches)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# เพิ่มเส้นทางสำหรับอัปเดตสถานะการจับคู่
@app.route('/update-match-status', methods=['POST'])
def update_match_status():
    try:
        data = request.json
        student_id = data.get('student_id')
        company_id = data.get('company_id')
        status = data.get('status')

        if not student_id or not company_id or not status:
            return jsonify({"error": "ต้องระบุข้อมูลให้ครบถ้วน"}), 400

        # อัปเดตสถานะการจับคู่
        result = match_collection.update_one(
            {
                "macth.student_id": student_id,
                "macth.company_id": company_id
            },
            {
                "$set": {"macth.status": status}
            }
        )

        if result.modified_count == 0:
            return jsonify({"error": "ไม่พบการจับคู่"}), 404

        return jsonify({"message": "อัปเดตสถานะสำเร็จ"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# เส้นทางสำหรับลบการจับคู่
@app.route('/remove-match/<student_id>', methods=['DELETE'])
def remove_match(student_id):
    try:
        # หาการจับคู่ก่อนลบเพื่อเอา company_id
        match = match_collection.find_one({"macth.student_id": student_id})
        
        if not match:
            return jsonify({"error": "ไม่พบการจับคู่"}), 404
            
        company_id = match["macth"]["company_id"]
        
        # ลบการจับคู่ตามรหัสนักศึกษา
        result = match_collection.delete_one({"macth.student_id": student_id})

        if result.deleted_count == 0:
            return jsonify({"error": "ไม่พบการจับคู่"}), 404
            
        # ลดจำนวนนักศึกษาที่ฝึกงานในบริษัทนั้น
        companies_collection.update_one(
            {"company_id": company_id},
            {"$inc": {"student_count": -1}}  # ลดค่า student_count ลง 1
        )

        return jsonify({"message": "ลบการจับคู่สำเร็จ"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/ranked-companies', methods=['POST'])
def get_ranked_companies():
    try:
        # รับข้อมูลทักษะของนักศึกษา
        data = request.json
        student_skills = data.get('student_skills', [])
        page = data.get('page', 1)
        per_page = data.get('per_page', 6)

        # ดึงข้อมูลบริษัททั้งหมด
        all_companies = companies_collection.find({}, {"_id": 0})
        
        # ฟังก์ชันคำนวณความตรงกันของทักษะ
        def calculate_skill_match(company_skills, student_skills):
            if not company_skills:
                return 0
            
            company_skill_list = [skill.strip() for skill in company_skills.split(',')]
            matched_skills = set(company_skill_list) & set(student_skills)
            
            # คำนวณเปอร์เซ็นต์การจับคู่ทักษะ
            match_percentage = (len(matched_skills) / len(company_skill_list)) * 100
            return match_percentage

        # จัดอันดับบริษัท
        ranked_companies = []
        for company in all_companies:
            company_data = company['company']
            skill_match = calculate_skill_match(
                company_data.get('qualifications', ''), 
                student_skills
            )
            
            ranked_companies.append({
                'company_id': company['company_id'],
                'company_info': company_data,
                'skill_match': skill_match
            })

        # เรียงลำดับตามการจับคู่ทักษะจากมากไปน้อย
        ranked_companies.sort(key=lambda x: x['skill_match'], reverse=True)

        # แบ่งหน้า
        start_index = (page - 1) * per_page
        end_index = start_index + per_page
        paginated_companies = ranked_companies[start_index:end_index]

        return jsonify({
            'companies': paginated_companies,
            'total_companies': len(ranked_companies),
            'total_pages': math.ceil(len(ranked_companies) / per_page),
            'current_page': page
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
    # เพิ่ม API endpoint สำหรับดึงจำนวนนักศึกษาแต่ละบริษัท
@app.route('/company-student-counts', methods=['GET'])
def get_company_student_counts():
    try:
        companies = []
        for company in companies_collection.find({}, {"_id": 0, "company_id": 1, "company.company_name": 1, "student_count": 1}):
            companies.append({
                "company_id": company["company_id"],
                "company_name": company["company"]["company_name"],
                "student_count": company.get("student_count", 0)  # ใช้ get เพื่อรองรับกรณีที่ยังไม่มีฟิลด์นี้
            })
        return jsonify(companies)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
        
# API สำหรับอัพเดทจำนวนนักศึกษาของบริษัททั้งหมด (สำหรับรัน 1 ครั้งเพื่ออัพเดทข้อมูลเก่า)
@app.route('/update-all-company-student-counts', methods=['POST'])
def update_all_company_student_counts():
    try:
        # รีเซ็ตจำนวนนักศึกษาของทุกบริษัทเป็น 0
        companies_collection.update_many(
            {},
            {"$set": {"student_count": 0}}
        )
        
        # นับจำนวนการจับคู่ของแต่ละบริษัท
        company_counts = {}
        for match in match_collection.find({}):
            company_id = match["macth"]["company_id"]
            if company_id in company_counts:
                company_counts[company_id] += 1
            else:
                company_counts[company_id] = 1
        
        # อัพเดทจำนวนนักศึกษาของแต่ละบริษัท
        for company_id, count in company_counts.items():
            companies_collection.update_one(
                {"company_id": company_id},
                {"$set": {"student_count": count}}
            )
            
        return jsonify({
            "message": "อัพเดทจำนวนนักศึกษาของทุกบริษัทเรียบร้อยแล้ว",
            "updated_companies": len(company_counts)
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
##############################################################################################################################################################################

# เพิ่มต่อจากส่วนเชื่อมต่อ MongoDB collections อื่นๆ
db_review = client["review"]  # database ชื่อ review
review_collection = db_review["review"]  # collection ชื่อ review

# เพิ่มรีวิวใหม่
@app.route('/add-review', methods=['POST'])
def add_review():
    try:
        data = request.json
        student_id = data.get('student_id')
        company_id = data.get('company_id')
        rating = data.get('rating')  # คะแนนดาว (1-5)
        comment = data.get('comment')  # ข้อความรีวิว
        reviewer_name = data.get('reviewer_name', 'Anonymous')  # ชื่อผู้รีวิว (ถ้าไม่ส่งมาให้ใช้ Anonymous)

        # ตรวจสอบข้อมูลที่จำเป็น
        if not student_id or not company_id or rating is None:
            return jsonify({"error": "กรุณาระบุข้อมูล student_id, company_id, และ rating ให้ครบถ้วน"}), 400

        # ตรวจสอบความถูกต้องของคะแนน
        if not isinstance(rating, (int, float)) or rating < 1 or rating > 5:
            return jsonify({"error": "คะแนนต้องอยู่ระหว่าง 1-5"}), 400

        # ตรวจสอบว่าเคยรีวิวแล้วหรือไม่
        existing_review = review_collection.find_one({
            "review.student_id": student_id,
            "review.company_id": company_id
        })

        # ถ้าเคยรีวิวแล้ว ทำการอัปเดต
        if existing_review:
            result = review_collection.update_one(
                {
                    "review.student_id": student_id,
                    "review.company_id": company_id
                },
                {
                    "$set": {
                        "review.rating": rating,
                        "review.comment": comment,
                        "review.updated_at": datetime.now().isoformat()
                    }
                }
            )
            return jsonify({"message": "อัปเดตรีวิวเรียบร้อยแล้ว", "review_id": existing_review["review_id"]}), 200

        # สร้างรีวิวใหม่
        review_id = str(random.randint(1000000000, 9999999999))
        new_review = {
            "review_id": review_id,
            "review": {
                "student_id": student_id,
                "company_id": company_id,
                "rating": rating,
                "comment": comment,
                "reviewer_name": reviewer_name,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
        }

        # บันทึกข้อมูลลงฐานข้อมูล
        review_collection.insert_one(new_review)

        return jsonify({
            "message": "เพิ่มรีวิวเรียบร้อยแล้ว",
            "review_id": review_id
        }), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ดึงรีวิวทั้งหมดของบริษัท
@app.route('/company-reviews/<company_id>', methods=['GET'])
def get_company_reviews(company_id):
    try:
        reviews = []
        # ดึงรีวิวทั้งหมดของบริษัท
        for review in review_collection.find({"review.company_id": company_id}, {"_id": 0}):
            reviews.append(review)
        
        # คำนวณคะแนนเฉลี่ย
        avg_rating = 0
        if reviews:
            total_rating = sum([review["review"]["rating"] for review in reviews])
            avg_rating = total_rating / len(reviews)
        
        return jsonify({
            "company_id": company_id,
            "average_rating": round(avg_rating, 1),
            "total_reviews": len(reviews),
            "reviews": reviews
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ดึงรีวิวของนักศึกษา
@app.route('/student-reviews/<student_id>', methods=['GET'])
def get_student_reviews(student_id):
    try:
        reviews = []
        # ดึงรีวิวทั้งหมดที่นักศึกษาเคยให้
        for review in review_collection.find({"review.student_id": student_id}, {"_id": 0}):
            reviews.append(review)
        
        return jsonify({
            "student_id": student_id,
            "total_reviews": len(reviews),
            "reviews": reviews
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ลบรีวิว
@app.route('/delete-review/<review_id>', methods=['DELETE'])
def delete_review(review_id):
    try:
        # ลบรีวิวตาม review_id
        result = review_collection.delete_one({"review_id": review_id})

        if result.deleted_count == 0:
            return jsonify({"error": "ไม่พบรีวิวที่ต้องการลบ"}), 404

        return jsonify({"message": "ลบรีวิวสำเร็จ"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# แก้ไข import ด้านบนเพิ่ม datetime
from datetime import datetime

# API สำหรับดึงข้อมูลสรุปคะแนนรีวิวของทุกบริษัท
@app.route('/all-companies-ratings', methods=['GET'])
def get_all_companies_ratings():
    try:
        # ดึงข้อมูลบริษัททั้งหมด
        all_companies = list(companies_collection.find({}, {"_id": 0}))
        companies_ratings = []
        
        for company in all_companies:
            company_id = company["company_id"]
            company_name = company["company"]["company_name"]
            
            # นับรีวิวและคำนวณคะแนนเฉลี่ย
            reviews = list(review_collection.find({"review.company_id": company_id}))
            total_reviews = len(reviews)
            avg_rating = 0
            
            if total_reviews > 0:
                total_rating = sum([review["review"]["rating"] for review in reviews])
                avg_rating = round(total_rating / total_reviews, 1)
            
            companies_ratings.append({
                "company_id": company_id,
                "company_name": company_name,
                "average_rating": avg_rating,
                "total_reviews": total_reviews
            })
        
        return jsonify(companies_ratings)

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
if __name__ == '__main__':
    app.run(debug=True, port=5000)