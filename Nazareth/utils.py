import africastalking
import string
import random
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

SENDER_ID = 'NazarethQMS'

def initialize_africas_talking():
    USERNAME = 'sandbox'
    API_KEY = 'atsk_73751c0014c74b42eb824d936515afdcdab3763881abd7a311a9ce0b289bef4c1e53b47a'
    africastalking.initialize(USERNAME, API_KEY)
    return africastalking.SMS

def send_payment_notification(phone_number, amount):
    message = f"Your consultation fee of {amount} KES has been successfully processed."
    try:
        response = initialize_africas_talking().send(message, [phone_number], SENDER_ID)
        logger.info(f"Message sent to {phone_number}: {message}")
        return response
    except Exception as e:
        logger.error(f"Failed to send payment notification: {str(e)}")
        return {"error": str(e)}

def generate_temp_password(length=8):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

def send_login_details(phone_number, username, temp_password):
    message = f"Your account has been created! Username: {username}, Password: {temp_password}"
    try:
        response = initialize_africas_talking().send(message, [phone_number], SENDER_ID)
        logger.info(f"Login details sent to {phone_number}: {message}")
        return response
    except Exception as e:
        logger.error(f"Failed to send login details: {str(e)}")
        return {"error": str(e)}
