import json
import requests
import random
from django.core.mail import send_mail
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render, reverse
from django.views.decorators.csrf import csrf_exempt

from .EmailBackend import EmailBackend
from .EmailBackend import EmailBackend
from .models import *
from django.contrib.auth.hashers import make_password, check_password
from django.core.files.storage import FileSystemStorage
# Create your views here.


def login_page(request):
    if request.user.is_authenticated:
        if request.user.user_type == '1':
            return redirect(reverse("admin_home"))
        elif request.user.user_type == '2':
            return redirect(reverse("staff_home"))
        else:
            return redirect(reverse("student_home"))
    return render(request, 'main_app/login.html')


def doLogin(request, **kwargs):
    if request.method != 'POST':
        return HttpResponse("<h4>Denied</h4>")
    else:

        
        #Authenticate
        #Authenticate
        email = request.POST.get('email')
        password = request.POST.get('password')
        user = EmailBackend.authenticate(request, username=email, password=password)
        if user != None:
            login(request, user)
            
            # Handle "Remember Me" functionality
            remember_me = request.POST.get('remember')
            if remember_me:
                # Set session to expire when browser closes = False
                # Session will last for 30 days
                request.session.set_expiry(30 * 24 * 60 * 60)  # 30 days in seconds
            else:
                # Set session to expire when browser closes
                request.session.set_expiry(0)
            
            if user.user_type == '1':
                return redirect(reverse("admin_home"))
            elif user.user_type == '2':
                return redirect(reverse("staff_home"))
            else:
                return redirect(reverse("student_home"))
        else:
            # Check if pending student
            pending = PendingStudent.objects.filter(email=email).first()
            if pending and check_password(password, pending.password):
                if pending.status == 'pending':
                    messages.error(request, "Your account is under review")
                elif pending.status == 'rejected':
                    messages.error(request, "Your registration was rejected")
                return redirect("/")
            else:
                messages.error(request, "Invalid details")
                return redirect("/")

def student_register(request):
    courses = Course.objects.all()
    sessions = Session.objects.all()
    context = {
        'courses': courses,
        'sessions': sessions
    }
    return render(request, 'main_app/student_register.html', context)

def do_student_register(request):
    if request.method != 'POST':
        return HttpResponse("Method not allowed")
    
    first_name = request.POST.get('first_name')
    last_name = request.POST.get('last_name')
    email = request.POST.get('email')
    mobile = request.POST.get('mobile')
    aadhaar_number = request.POST.get('aadhaar_number')
    course_id = request.POST.get('course')
    session_id = request.POST.get('session')
    password = request.POST.get('password')
    aadhaar_image = request.FILES.get('aadhaar_image')
    
    # Check if user exists
    if CustomUser.objects.filter(email=email).exists() or PendingStudent.objects.filter(email=email).exists():
        messages.error(request, "Email already exists!")
        return redirect('student_register')
        
    try:
        # Generate OTP
        otp = str(random.randint(100000, 999999))
        
        # Save Aadhaar image temporarily if exists
        aadhaar_filename = ""
        if aadhaar_image:
            fs = FileSystemStorage()
            aadhaar_filename = fs.save('aadhaar_images/' + aadhaar_image.name, aadhaar_image)
            
        # Store in session
        request.session['registration_data'] = {
            'first_name': first_name,
            'last_name': last_name,
            'email': email,
            'mobile': mobile,
            'aadhaar_number': aadhaar_number,
            'course_id': course_id,
            'session_id': session_id,
            'password': password,
            'aadhaar_filename': aadhaar_filename
        }
        request.session['registration_otp'] = otp
        
        # Send Email
        html_content = f"""
        <div style="font-family: Arial, sans-serif; padding: 20px; color: #333;">
          <h2 style="color: #2c7be5;">Nersha ERP System</h2>
          <p>Hello <strong>{first_name} {last_name}</strong>,</p>
          <p>Thank you for registering with <strong>Nersha ERP System</strong>.</p>
          <p>To complete your registration, please use the One-Time Password (OTP) below:</p>
          <h1 style="letter-spacing: 6px; color: #000;">{otp}</h1>
          <p>This OTP is valid for <strong>5 minutes</strong>.</p>
          <p style="color: red;"><strong>Warning:</strong> Do not share this OTP with anyone. Nersha ERP System will never ask for your OTP.</p>
          <hr>
          <p style="font-size: 12px; color: gray;">
            If you did not initiate this request, please ignore this email.
          </p>
          <p>Regards,<br><strong>Nersha ERP System Team</strong></p>
        </div>
        """
        send_mail(
            subject="Nersha ERP System - Email Verification",
            message=f"Your OTP is {otp}",
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[email],
            html_message=html_content,
            fail_silently=False,
        )
        
        messages.success(request, "OTP sent to your email. Please verify.")
        return redirect('verify_otp')
    except Exception as e:
        messages.error(request, f"Registration failed: {str(e)}")
        return redirect('student_register')


def verify_otp(request):
    if request.method == 'GET':
        if 'registration_data' not in request.session:
            messages.error(request, "No pending registration found.")
            return redirect('student_register')
        return render(request, 'main_app/verify_otp.html')
        
    elif request.method == 'POST':
        user_otp = request.POST.get('otp')
        session_otp = request.session.get('registration_otp')
        
        if str(user_otp) == str(session_otp):
            # Success, save the PendingStudent to database
            data = request.session.get('registration_data')
            try:
                course = Course.objects.get(id=data['course_id'])
                batch = Session.objects.get(id=data['session_id'])
                
                pending_student = PendingStudent(
                    first_name=data['first_name'],
                    last_name=data['last_name'],
                    email=data['email'],
                    mobile_number=data['mobile'],
                    aadhaar_number=data['aadhaar_number'],
                    course_type=course,
                    batch=batch,
                    password=make_password(data['password']),
                    status='pending',
                    aadhaar_image=data['aadhaar_filename']
                )
                pending_student.save()
                
                # Clear session
                del request.session['registration_data']
                del request.session['registration_otp']
                
                messages.success(request, "Registration successful! Your account is now under review by the Administrator.")
                return redirect('login_page')
            except Exception as e:
                messages.error(request, f"Error saving registration: {str(e)}")
                return redirect('student_register')
        else:
            messages.error(request, "Invalid OTP. Please try again.")
            return render(request, 'main_app/verify_otp.html')




def logout_user(request):
    if request.user != None:
        logout(request)
    return redirect("/")


@csrf_exempt
def get_attendance(request):
    subject_id = request.POST.get('subject')
    session_id = request.POST.get('session')
    try:
        subject = get_object_or_404(Subject, id=subject_id)
        session = get_object_or_404(Session, id=session_id)
        attendance = Attendance.objects.filter(subject=subject, session=session)
        attendance_list = []
        for attd in attendance:
            data = {
                    "id": attd.id,
                    "attendance_date": str(attd.date),
                    "session": attd.session.id
                    }
            attendance_list.append(data)
        return JsonResponse(json.dumps(attendance_list), safe=False)
    except Exception as e:
        return None


def showFirebaseJS(request):
    data = """
    // Give the service worker access to Firebase Messaging.
// Note that you can only use Firebase Messaging here, other Firebase libraries
// are not available in the service worker.
importScripts('https://www.gstatic.com/firebasejs/7.22.1/firebase-app.js');
importScripts('https://www.gstatic.com/firebasejs/7.22.1/firebase-messaging.js');

// Initialize the Firebase app in the service worker by passing in
// your app's Firebase config object.
// https://firebase.google.com/docs/web/setup#config-object
firebase.initializeApp({
    apiKey: "AIzaSyBarDWWHTfTMSrtc5Lj3Cdw5dEvjAkFwtM",
    authDomain: "sms-with-django.firebaseapp.com",
    databaseURL: "https://sms-with-django.firebaseio.com",
    projectId: "sms-with-django",
    storageBucket: "sms-with-django.appspot.com",
    messagingSenderId: "945324593139",
    appId: "1:945324593139:web:03fa99a8854bbd38420c86",
    measurementId: "G-2F2RXTL9GT"
});

// Retrieve an instance of Firebase Messaging so that it can handle background
// messages.
const messaging = firebase.messaging();
messaging.setBackgroundMessageHandler(function (payload) {
    const notification = JSON.parse(payload);
    const notificationOption = {
        body: notification.body,
        icon: notification.icon
    }
    return self.registration.showNotification(payload.notification.title, notificationOption);
});
    """
    return HttpResponse(data, content_type='application/javascript')

