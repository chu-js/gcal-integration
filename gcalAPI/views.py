from __future__ import print_function

# Packages for Django
from django.shortcuts import render
from django.http import JsonResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response

# Packages for GCal API
from pprint import pprint
from datetime import datetime, time, timedelta
from pytz import timezone, utc

import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import firebase_admin
from firebase_admin import auth
from firebase_admin import credentials

cred = credentials.Certificate("service-account-private-key.json") # Removed: service-account-private-key.json

# Initialise the Firebase admin SDK
default_app = firebase_admin.initialize_app(cred)

# Function: Initialise Google Calendar API service
def initialise_service():
    SCOPES = ['https://www.googleapis.com/auth/calendar']

    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first time.

    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES) # Removed: token.json from file

    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    try:
        service = build('calendar', 'v3', credentials=creds)
        print('service created successfully')
        return service

    except HttpError as error:
        print('An error occurred: %s' % error)

# Variable: Define calendar_id
calendar_id = "" # Removed: calendar ID

# Variable: Define timezone we are in
SGT_tz = timezone('Asia/Singapore')

# Function: Convert UTC ISOFormat string returned from Google Calendar to SGT datetime object
def convert_UTC_isoformat_to_SGT_datetime(isoformat_string):
    UTC_datetime = datetime.fromisoformat(isoformat_string)
    SGT_datetime = UTC_datetime.replace(tzinfo=utc).astimezone(SGT_tz)
    return SGT_datetime

# Function: Convert UTC date string returned from Google Calendar to SGT datetime object
def convert_UTC_date_string_to_SGT_datetime(date_string):
    date = datetime.strptime(date_string, '%Y-%m-%d').astimezone(SGT_tz)
    SGT_datetime = date + timedelta(hours=0, minutes=0)

    return SGT_datetime

# Function: Convert SGT ISOFormat string to SGT datetime object
def convert_SGT_isoformat_to_SGT_datetime(isoformat_string):
    SGT_datetime = datetime.fromisoformat(isoformat_string)
    SGT_datetime = SGT_datetime.astimezone(SGT_tz)
    return SGT_datetime

# Function: Convert datetime object to SGT ISOFormat string
def convert_datetime_to_SGT_isoformat(date, time):
    SGT_isoformat = SGT_tz.localize(datetime.combine(date, time)).isoformat()
    return SGT_isoformat

# Function: Generate slot to be evaluated
def generate_slot_for_evaluation(start_date, booking_slot):
    # Combine date and time for datetime slot to be evaluated
    start_datetime = SGT_tz.localize(datetime.combine(start_date, booking_slot['start_time']))
    end_datetime = start_datetime + booking_slot['duration']
    event = {
        'start': {
            'dateTime': start_datetime.isoformat(),
            'timeZone': 'Asia/Singapore',
        },
        'end': {
            'dateTime': end_datetime.isoformat(),
            'timeZone': 'Asia/Singapore',
        },
    }

    return event

# Function: Check if half-day slot is available (for GET and POST requests)
# Returns a boolean
def is_half_day_slot_available(service, calendar_id, start_time, end_time):
    # Exclude all Sundays
    if convert_SGT_isoformat_to_SGT_datetime(start_time).weekday() != 6:
        try:
            # List all events during this period
            event_details = service.events().list(calendarId=calendar_id,
                                                    timeMin=start_time, timeMax=end_time).execute().get('items')
                        
            if len(event_details) < 4:
                return True

            else:  
                return False

        except HttpError as error:
            print(f'An error occurred: {error}')
    else:
        return False

# Function: Generate available half-day slots (for GET request only)
# Returns SGT ISOFormat string
def generate_available_half_day_slots(service, calendar_id, start_date, booking_slot, available_slots):
        # Generate slot for evaluation of availability
        event = generate_slot_for_evaluation(start_date, booking_slot)

        if is_half_day_slot_available(service, calendar_id, event['start']['dateTime'], event['end']['dateTime']) == True:
            available_slots.append(
                    {'start': event['start']['dateTime'], 'end': event['end']['dateTime']})

# Function: Check if full-day slot is available (for GET and POST requests)
# Returns a boolean
def is_full_day_slot_available(service, calendar_id, start_time, end_time):
    # Exclude all Sundays
    if convert_SGT_isoformat_to_SGT_datetime(start_time).weekday() != 6:
        morning_slot_count = 0
        afternoon_slot_count = 0
        full_day_count = 0

        try:
            # List all events during this period
            event_details = service.events().list(calendarId=calendar_id,
                                                timeMin=start_time, timeMax=end_time).execute().get('items')

            for existing_event in event_details:
                if 'start' in existing_event and 'date' in existing_event['start'] and 'end' in existing_event and 'date' in existing_event['end']:
                    existing_booking_start_datetime = convert_UTC_date_string_to_SGT_datetime(existing_event['start']['date'])
                    existing_booking_end_datetime = convert_UTC_date_string_to_SGT_datetime(existing_event['end']['date'])
                else: 
                    existing_booking_start_datetime = convert_UTC_isoformat_to_SGT_datetime(existing_event['start']['dateTime'])
                    existing_booking_end_datetime = convert_UTC_isoformat_to_SGT_datetime(existing_event['end']['dateTime'])

                duration = existing_booking_end_datetime - existing_booking_start_datetime

                if duration < timedelta(hours=5):
                    if existing_booking_end_datetime.time() < time(hour=14):
                        morning_slot_count += 1
                    elif existing_booking_end_datetime.time() > time(hour=14):
                        afternoon_slot_count += 1
                elif duration > timedelta(hours=5):
                    full_day_count += 1

            if full_day_count + morning_slot_count < 4 and full_day_count + afternoon_slot_count < 4:
                return True
            
            else:  
                return False
        
        except HttpError as error:
            print(f'An error occurred: {error}')
    else:
        return False
    
# Function: Generate available full-day slots (for GET request only)
# Returns a date object
def generate_available_full_day_slots(service, calendar_id, start_date, booking_slot, available_days):
    # Generate slot for evaluation of availability
    event = generate_slot_for_evaluation(start_date, booking_slot)

    if is_full_day_slot_available(service, calendar_id, event['start']['dateTime'], event['end']['dateTime']) == True:
        available_days.append(start_date)

# Function: Check if consecutive-day slot is available (for POST request only)
def is_consecutive_days_slot_available(service, calendar_id, start_time, no_of_days):
    start_time_SGT_datetime = convert_SGT_isoformat_to_SGT_datetime(start_time)
    proceed_with_booking_array = []
    for day in range(no_of_days):
        slot_start_time = start_time_SGT_datetime + timedelta(days=day)
        slot_end_time = slot_start_time + timedelta(hours=9)
        proceed_with_booking_array.append(is_full_day_slot_available(service, calendar_id, datetime.isoformat(slot_start_time), datetime.isoformat(slot_end_time)))
    proceed_with_booking = all(proceed_with_booking_array)
    
    return proceed_with_booking

# Function: Check if x.5-day slot is available (for POST request only)
def is_x_and_half_days_slot_available(service, calendar_id, start_time, no_of_days):
    start_time_SGT_datetime = convert_SGT_isoformat_to_SGT_datetime(start_time)

    # Evaluate availability of full-day slots
    # Create interim array to store boolean for whether full-day slots are available, equivalent of proceed_with_booking_array in the other functions
    are_full_day_slots_available = []
    for day in range(no_of_days):
        full_day_slot_start_time = start_time_SGT_datetime + timedelta(days=day)
        full_day_slot_end_time = full_day_slot_start_time + timedelta(hours=9)
        are_full_day_slots_available.append(is_full_day_slot_available(service, calendar_id, datetime.isoformat(full_day_slot_start_time), datetime.isoformat(full_day_slot_end_time)))
    
    # Evaluate availability of last morning half-day slot
    morning_slot_start_time = start_time_SGT_datetime + timedelta(days=no_of_days)
    morning_slot_end_time = morning_slot_start_time + timedelta(hours=4)
    is_morning_slot_available = is_half_day_slot_available(service, calendar_id, datetime.isoformat(morning_slot_start_time), datetime.isoformat(morning_slot_end_time))

    if all(are_full_day_slots_available) and is_morning_slot_available:
        proceed_with_booking = True
    else:
        proceed_with_booking = False
    
    return proceed_with_booking

# View: Get available timeslots from the calendar if there are more than 1 resource
@api_view(['GET'])
def get_available_slots(request):
    service = initialise_service()

    # Extract slot type from POST request: 0.5, 1, 2, 3, 1.5, 2.5, 3.5 days
    slot_type = float(request.GET.get('slot_type'))

    # Search for availability starting 4 days from today
    display_start_date = datetime.now().date() + timedelta(days=4)

    # Create array to store available slots
    available_slots = []
    # Create interim array to store available days to evaluate available full-day slots
    available_days = []
    # Create interim array to store available morning slots to evaluate available x.5-day slots
    available_morning_slots = []

    # Returns ISOFormat string
    if slot_type == 0.5:
        # The timeslots start at either 9AM or 2:30PM and each slot lasts for 4 hours.
        booking_slots = [{'start_time': time(hour=9), 'duration': timedelta(hours=4)},
                         {'start_time': time(hour=14, minute=30), 'duration': timedelta(hours=4)}]

        # Find available half-day slots for the next 14 days from display_start_date
        for day in range(14):
            for booking_slot in booking_slots:
                # Start date
                start_date = display_start_date + timedelta(days=day)

                generate_available_half_day_slots(service, calendar_id, start_date, booking_slot, available_slots)

    elif slot_type == 1 or slot_type == 2 or slot_type == 3:

        # The timeslots start at 9AM and each slot lasts for 9 hours.
        booking_slot = {'start_time': time(hour=9), 'duration': timedelta(hours=9)}

        # Find available full-day slots for the next 14 days
        for day in range(14):
            # Start date
            start_date = display_start_date + timedelta(days=day)

            generate_available_full_day_slots(service, calendar_id, start_date, booking_slot, available_days)
        
        if slot_type == 1: 
            for day in available_days:
                start_SGT_isoformat = convert_datetime_to_SGT_isoformat(day, time(hour=9))
                end_SGT_isoformat = convert_datetime_to_SGT_isoformat(day, time(hour=18))
                available_slots.append({'start': start_SGT_isoformat, 'end': end_SGT_isoformat})

        elif slot_type == 2:
            for day in available_days:
                if day + timedelta(days=1) in available_days:
                    start_SGT_isoformat = convert_datetime_to_SGT_isoformat(day, time(hour=9))
                    end_SGT_isoformat = convert_datetime_to_SGT_isoformat(day + timedelta(days=1), time(hour=18))
                    available_slots.append({'start': start_SGT_isoformat, 'end': end_SGT_isoformat})

        elif slot_type == 3:
            for day in available_days:
                if day + timedelta(days=1) in available_days and day + timedelta(days=2) in available_days:
                    start_SGT_isoformat = convert_datetime_to_SGT_isoformat(day, time(hour=9))
                    end_SGT_isoformat = convert_datetime_to_SGT_isoformat(day + timedelta(days=2), time(hour=18))
                    available_slots.append({'start': start_SGT_isoformat, 'end': end_SGT_isoformat})

                
    # Returns date object
    elif slot_type == 1.5 or slot_type == 2.5 or slot_type == 3.5:

        # There are 2 parts to this: 
        # 1. I need to first create an array of all available full consecutive day slots.
        # 2. I also need to create an array of all available morning half-day slots.

        # 1. I need to first create an array of all available full consecutive day slots.
        # The timeslots start at 9AM and each slot lasts for 9 hours.
        full_day_booking_slot = {'start_time': time(hour=9), 'duration': timedelta(hours=9)}

        # Find available full-day slots for the next 14 days
        for day in range(14):
            # Start date
            start_date = display_start_date + timedelta(days=day)

            generate_available_full_day_slots(service, calendar_id, start_date, full_day_booking_slot, available_days)
        
        # 2. I also need to create an array of all available morning half-day slots.
        # The timeslots start at 9AM and each slot lasts for 4 hours.
        morning_half_day_booking_slot = {'start_time': time(hour=9), 'duration': timedelta(hours=4)}

        # Find available half-day slots for the next 14 days from display_start_date
        for day in range(14):
            # Start date
            start_date = display_start_date + timedelta(days=day)

            generate_available_half_day_slots(service, calendar_id, start_date, morning_half_day_booking_slot, available_morning_slots)

        if slot_type == 1.5:
            # I need to evaluate for each available day, whether there is a corresponding available morning half-day slot the next day.
            for day in available_days:
                next_morning_slot_in_SGT_ISOFormat = convert_datetime_to_SGT_isoformat(day + timedelta(days=1), morning_half_day_booking_slot['start_time'])
                for slot in available_morning_slots:
                    if next_morning_slot_in_SGT_ISOFormat == slot['start']:
                        start_SGT_isoformat = convert_datetime_to_SGT_isoformat(day, time(hour=9))
                        end_SGT_isoformat = convert_datetime_to_SGT_isoformat(day + timedelta(days=1), time(hour=12, minute=30))
                        available_slots.append({'start': start_SGT_isoformat, 'end': end_SGT_isoformat})
                    
        # Returns date object
        elif slot_type == 2.5:
            # I need to evaluate for each available day, whether there is a corresponding available morning half-day slot the next day.               
            for day in available_days:
                # Evaluate if 2nd consecutive day is available.
                if day + timedelta(days=1) in available_days:
                    # Evaluate if 3rd consecutive morning slot is available.
                    next_morning_slot_in_SGT_ISOFormat = convert_datetime_to_SGT_isoformat(day + timedelta(days=2), morning_half_day_booking_slot['start_time'])
                    for slot in available_morning_slots:
                        if next_morning_slot_in_SGT_ISOFormat == slot['start']:
                            start_SGT_isoformat = convert_datetime_to_SGT_isoformat(day, time(hour=9))
                            end_SGT_isoformat = convert_datetime_to_SGT_isoformat(day + timedelta(days=2), time(hour=12, minute=30))
                            available_slots.append({'start': start_SGT_isoformat, 'end': end_SGT_isoformat})
                            
        elif slot_type == 3.5:
            # I need to evaluate for each available day, whether there is a corresponding available morning half-day slot the next day.               
            for day in available_days:
                # Evaluate if 2nd and 3rd consecutive day are available.
                if day + timedelta(days=1) in available_days and day + timedelta(days=2) in available_days:
                    # Evaluate if 4th consecutive morning slot is available.
                    next_morning_slot_in_SGT_ISOFormat = convert_datetime_to_SGT_isoformat(day + timedelta(days=3), morning_half_day_booking_slot['start_time'])
                    for slot in available_morning_slots:
                        if next_morning_slot_in_SGT_ISOFormat == slot['start']:
                            start_SGT_isoformat = convert_datetime_to_SGT_isoformat(day, time(hour=9))
                            end_SGT_isoformat = convert_datetime_to_SGT_isoformat(day + timedelta(days=3), time(hour=12, minute=30))
                            available_slots.append({'start': start_SGT_isoformat, 'end': end_SGT_isoformat})
                        
    return Response(available_slots)

# View: Post booking
@api_view(['POST'])
def book_slot(request):
    service = initialise_service()

    # Extract booking information from POST request
    request_data = request.data

    slot_type = float(request_data['slot_type'])

    addons_array = []
    for key, value in request_data["selectedOptions"].items():
        if 'add_on_title' in value and 'option' in value:
            addons_array.append(value['add_on_title'] + ': ' + value['option'])

    addons = '\n'.join(addons_array)  
    
    # Check against Google Calendar if slot is available
    if slot_type == 0.5:
        proceed_with_booking = is_half_day_slot_available(service, calendar_id, request_data['selectedTimeslot']['start'], request_data['selectedTimeslot']['end'])
    
    elif slot_type == 1:
        proceed_with_booking = is_full_day_slot_available(service, calendar_id, request_data['selectedTimeslot']['start'], request_data['selectedTimeslot']['end'])

    elif slot_type == 2 or slot_type == 3:
        proceed_with_booking = is_consecutive_days_slot_available(service, calendar_id, request_data['selectedTimeslot']['start'], int(slot_type))

    elif slot_type == 1.5 or slot_type == 2.5 or slot_type == 3.5:
        proceed_with_booking = is_x_and_half_days_slot_available(service, calendar_id, request_data['selectedTimeslot']['start'], int(slot_type - 0.5))
    
    # Proceed with booking only if slot is still available. Otherwise, throw an error.
    if proceed_with_booking:
        event_request = {
            'start': {
                'dateTime': request_data['selectedTimeslot']['start'],
                'timeZone': 'Asia/Singapore'
            },
            'end': {
                'dateTime': request_data['selectedTimeslot']['end'],
                'timeZone': 'Asia/Singapore'
            },
            'summary': '[' + request_data['status'] + '] ' + request_data['customer_name'] + ": " + request_data['product_name'],
            'description':  'Customer Name: ' + request_data['customer_name'] + '\nProduct: ' + request_data['product_name'] + '\nAdd-ons:\n' + addons + '\nPrice: $' + str(request_data['totalPrice']) + "\nBooked from website",
            # + '\nAdditional notes: ' + request_data['additional_notes']
            # '\nCustomer HP: ' + request_data['customer_hp'] +
            'colorId': 1,
            'status': 'confirmed',
            'transparency': 'opaque',
            'visibility': 'private',
        }

        send_notifications = True
        send_updates = 'all'    
        created_event = service.events().insert(
            calendarId=calendar_id,
            sendNotifications=send_notifications,
            sendUpdates=send_updates,
            body=event_request
        ).execute()

    else:
        raise Exception("The slot is not available.")

    return Response(created_event)

# View: Update booking that is already added to cart, but payment not made
@api_view(['POST'])
def update_booking(request):
    service = initialise_service()

    # Extract booking information from POST request
    request_data = request.data

    # List all events to look for the one that you want to update
    event_details = service.events().list(calendarId=calendar_id, timeMin=request_data['start'], timeMax=request_data['end']).execute().get('items')

    # Find the event
    # To-do: I have no idea what will be the reference point
    updating_event = filter(lambda x: '1234567890' in x['description'], event_details)
    updating_event = next(updating_event)

    # Update the event
    updating_event['summary'] = '[completed] simple toilet reno'
    updating_event['colorId'] = 2

    service.events().update(
        calendarId=calendar_id,
        eventId=updating_event['id'],
        body=updating_event
    ).execute()

# Test View: Do something if the user is authenticated
@api_view(['GET'])
def auth_test(request):
# Get the Authorization header from the request
    auth_header = request.headers.get('Authorization')
    
    if not auth_header:
        # Return an error response if the Authorization header is missing
        return JsonResponse({'error': 'Authorization header missing'}, status=401)

    # Extract the user ID token from the Authorization header
    id_token = auth_header.split(' ')[1]

    try:
        # Verify the user ID token using the Firebase Admin SDK
        decoded_token = auth.verify_id_token(id_token)

        # Extract the user ID from the decoded token
        user_id = decoded_token['uid']

        # Allow the API call to proceed if the user is authenticated
        # You can add your API logic here
        return JsonResponse({'message': 'Authenticated user', 'user_id': user_id})

    except auth.InvalidIdTokenError:
        # Return an error response if the user ID token is invalid
        return JsonResponse({'error': 'Invalid user ID token'}, status=401)