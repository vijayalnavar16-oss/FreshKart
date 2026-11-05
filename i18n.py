"""Interface labels. Kannada is the default. Missing keys fall back to English."""
from flask import session

LANGS = {"kn": "ಕನ್ನಡ", "en": "English"}

STRINGS = {
    "kn": {
        "market": "ರೈತ ಮಾರುಕಟ್ಟೆ",
        "welcome": "ಸ್ವಾಗತ",
        "home": "ಮುಖಪುಟ",
        "orders": "ಆರ್ಡರ್‌ಗಳು",
        "cart": "ಕಾರ್ಟ್",
        "products": "ತರಕಾರಿಗಳು",
        "users": "ಬಳಕೆದಾರರು",
        "login": "ಲಾಗಿನ್",
        "logout": "ಲಾಗ್ ಔಟ್",
        "confirm_logout": "ನೀವು ಲಾಗ್ ಔಟ್ ಆಗಲು ಖಚಿತವಾಗಿದ್ದೀರಾ?",
        "username": "ಬಳಕೆದಾರ ಹೆಸರು",
        "password": "ಪಾಸ್‌ವರ್ಡ್",
        "role": "ಪಾತ್ರ",
        "accounts_note": "ಖಾತೆಗಳನ್ನು ನಿರ್ವಾಹಕರು ರಚಿಸುತ್ತಾರೆ.",
        "bad_login": "ಬಳಕೆದಾರ ಹೆಸರು ಅಥವಾ ಪಾಸ್‌ವರ್ಡ್ ತಪ್ಪಾಗಿದೆ.",
    },
    "en": {
        "market": "Raitha Market",
        "welcome": "Welcome",
        "home": "Home",
        "orders": "Orders",
        "cart": "Cart",
        "products": "Vegetables",
        "users": "Users",
        "login": "Login",
        "logout": "Logout",
        "confirm_logout": "Are you sure you want to log out?",
        "username": "Username",
        "password": "Password",
        "role": "Role",
        "accounts_note": "Accounts are created by the FreshKart administrator.",
        "bad_login": "Invalid username or password.",
    },
}


def t(key):
    lang = session.get("lang", "kn")
    return STRINGS.get(lang, STRINGS["en"]).get(key, STRINGS["en"].get(key, key))
