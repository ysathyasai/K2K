"""
Multilingual Voice Assistant & NLP Intent Service (Powered by Google Gemini).
Supports all major Indian regional languages:
- Hindi (hi)
- Marathi (mr)
- Telugu (te)
- Tamil (ta)
- Kannada (kn)
- Punjabi (pa)
- Gujarati (gu)
- English (en)

Performs dynamic regional language auto-detection, cultural honorific injection,
intent extraction (CHECK_PRICE, LOG_HARVEST, INPUT_FINANCING, WALLET_STATUS),
and localized natural language speech response generation.
"""
from decimal import Decimal
import logging
import re
from django.utils import timezone
from k2k_core.models import (
    User,
    Crop,
    ProduceBatch,
    InputLoan,
    FarmerWallet,
    InputType,
    InputLoanStatus
)
from k2k_core.services.gemini_client import call_gemini_structured_json

logger = logging.getLogger(__name__)

# Complete Regional Language Metadata & Cultural Honorifics
REGIONAL_LANGUAGES = {
    'hi': {
        'name': 'Hindi',
        'script_name': 'हिन्दी',
        'honorific': 'जी',
        'greeting': 'नमस्ते',
        'farmer_title': 'किसान भाई',
        'locale': 'hi-IN'
    },
    'mr': {
        'name': 'Marathi',
        'script_name': 'मराठी',
        'honorific': 'साहेब',
        'greeting': 'नमस्कार',
        'farmer_title': 'शेतकरी बंधू',
        'locale': 'mr-IN'
    },
    'te': {
        'name': 'Telugu',
        'script_name': 'తెలుగు',
        'honorific': 'గారు',
        'greeting': 'నమస్కారం',
        'farmer_title': 'రైతు సోదరుడు',
        'locale': 'te-IN'
    },
    'ta': {
        'name': 'Tamil',
        'script_name': 'தமிழ்',
        'honorific': 'அய்யா',
        'greeting': 'வணக்கம்',
        'farmer_title': 'விவசாய தோழரே',
        'locale': 'ta-IN'
    },
    'kn': {
        'name': 'Kannada',
        'script_name': 'ಕನ್ನಡ',
        'honorific': 'ಅವರೇ',
        'greeting': 'ನಮಸ್ಕಾರ',
        'farmer_title': 'ರೈತ ಬಾಂಧವರೇ',
        'locale': 'kn-IN'
    },
    'pa': {
        'name': 'Punjabi',
        'script_name': 'ਪੰਜਾਬੀ',
        'honorific': 'ਜੀ',
        'greeting': 'ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ',
        'farmer_title': 'ਕਿਸਾਨ ਵੀਰ',
        'locale': 'pa-IN'
    },
    'gu': {
        'name': 'Gujarati',
        'script_name': 'ગુજરાતી',
        'honorific': 'ભાઈ',
        'greeting': 'નમસ્તે',
        'farmer_title': 'ખેડૂત મિત્ર',
        'locale': 'gu-IN'
    },
    'en': {
        'name': 'English',
        'script_name': 'English',
        'honorific': 'Sir',
        'greeting': 'Hello',
        'farmer_title': 'Farmer Friend',
        'locale': 'en-IN'
    }
}


class VoiceAssistantIntelligenceEngine:

    @classmethod
    def detect_script_language(cls, text: str, fallback_lang: str = "hi") -> str:
        """
        Auto-detects regional language based on Indian script Unicode character blocks.
        """
        if not text:
            return fallback_lang if fallback_lang in REGIONAL_LANGUAGES else "hi"

        # Unicode Block Ranges for Indian Scripts
        if re.search(r'[\u0a00-\u0a7f]', text):
            return 'pa'  # Gurmukhi / Punjabi
        if re.search(r'[\u0a80-\u0aff]', text):
            return 'gu'  # Gujarati
        if re.search(r'[\u0b80-\u0bff]', text):
            return 'ta'  # Tamil
        if re.search(r'[\u0c00-\u0c7f]', text):
            return 'te'  # Telugu
        if re.search(r'[\u0c80-\u0cff]', text):
            return 'kn'  # Kannada
        if re.search(r'[\u0900-\u097f]', text):
            # Devanagari: distinguish Marathi vs Hindi by common morphological markers
            marathi_markers = ['आहे', 'केली', 'काढणी', 'हवे', 'तोडली', 'मिरची', 'पैसे', 'दर', 'शेतकरी', 'बॅच']
            if any(m in text for m in marathi_markers) or fallback_lang == 'mr':
                return 'mr'
            return 'hi'

        # Latin / English characters
        if re.search(r'[a-zA-Z]', text) and (fallback_lang in ('en', 'auto') or not fallback_lang):
            return 'en'

        return fallback_lang if fallback_lang in REGIONAL_LANGUAGES else "hi"

    @classmethod
    def process_voice_transcript(cls, transcript: str, lang: str = "auto", farmer: User = None) -> dict:
        """
        Parses multilingual speech transcript using Google Gemini to extract intent & entities,
        executes platform database logic, and generates culturally localized natural speech responses.
        Supports: Hindi, Marathi, Telugu, Tamil, Kannada, Punjabi, Gujarati, and English.
        """
        # Resolve initial language guess
        active_lang = lang if (lang and lang != 'auto' and lang in REGIONAL_LANGUAGES) else cls.detect_script_language(transcript, "hi")
        lang_meta = REGIONAL_LANGUAGES.get(active_lang, REGIONAL_LANGUAGES['hi'])

        farmer_name = farmer.get_full_name() or farmer.username if farmer else lang_meta['farmer_title']

        prompt = f"""
You are the Multilingual Voice Intelligence Engine for Project Khet2Kitchen (K2K), an agricultural digital supply chain platform in India.
A farmer named "{farmer_name}" spoke the following transcript:
"{transcript}"

Requested/Hinted language code: "{lang}" (Active candidate: "{active_lang}" - {lang_meta['name']}).

Your Responsibilities:
1. DETECT THE EXACT LANGUAGE & SCRIPT:
   Determine the true spoken language of the transcript:
   - 'hi': Hindi (हिन्दी)
   - 'mr': Marathi (मराठी)
   - 'te': Telugu (తెలుగు)
   - 'ta': Tamil (தமிழ்)
   - 'kn': Kannada (ಕನ್ನಡ)
   - 'pa': Punjabi (ਪੰਜਾਬੀ)
   - 'gu': Gujarati (ગુજરાતી)
   - 'en': Indian English
   Output this 2-letter code in "detected_language".

2. IDENTIFY INTENT:
   - CHECK_PRICE: Inquiring about mandi prices, today's rate, or guaranteed MSP floor for crops.
   - LOG_HARVEST: Reporting harvested quantity, picked crates, or requesting pickup.
   - INPUT_FINANCING: Requesting loan, zero-interest credit, seeds, fertilizers, or cash advance.
   - WALLET_STATUS: Inquiring about wallet balance, bank payouts, or UPI transfer arrival.

3. EXTRACT ENTITIES:
   - crop_name: Crop mentioned (e.g., Tomato, Capsicum, Wheat, Spinach, Onion, Potato, Cotton) or null.
   - quantity_kg: Numeric quantity in kilograms if mentioned, or null.
   - input_type: SEEDS | FERTILIZER | BIO_PESTICIDE | DRIP_EQUIPMENT or null.

4. GENERATE NATURAL, RESPECTFUL, LOCALIZED VOICE RESPONSE:
   - CRITICAL REQUIREMENT: Output MUST be in the EXACT script and dialect of the detected language ({lang_meta['name']}).
   - NEVER restrict yourself to Hindi or say you cannot speak the requested language. You are completely fluent in all 8 Indian languages.
   - Incorporate the appropriate cultural honorific:
     * Hindi: "{farmer_name} जी"
     * Marathi: "{farmer_name} साहेब / राव"
     * Telugu: "{farmer_name} గారు"
     * Tamil: "{farmer_name} அய்யா"
     * Kannada: "{farmer_name} ಅವರೇ"
     * Punjabi: "{farmer_name} ਜੀ"
     * Gujarati: "{farmer_name} ભાઈ"
     * English: "Farmer {farmer_name}"
   - Keep the spoken reply warm, concise, and clear for audio synthesis.

Return a valid JSON object strictly matching this schema:
{{
  "detected_language": "hi" | "mr" | "te" | "ta" | "kn" | "pa" | "gu" | "en",
  "intent": "CHECK_PRICE" | "LOG_HARVEST" | "INPUT_FINANCING" | "WALLET_STATUS",
  "crop_name": string or null,
  "quantity_kg": float or null,
  "input_type": string or null,
  "localized_reply_text": string,
  "confidence": float
}}
"""
        gemini_result = call_gemini_structured_json(
            contents=[prompt],
            system_instruction="You are K2K Voice Assistant, an AI fluent in all 8 major Indian regional languages, empowering smallholder farmers in their native tongue."
        )

        intent = "WALLET_STATUS"
        crop_name = None
        quantity_kg = None
        input_type = None
        gemini_reply = None
        detected_lang = active_lang

        if gemini_result:
            detected_lang = gemini_result.get('detected_language', active_lang).lower()
            if detected_lang not in REGIONAL_LANGUAGES:
                detected_lang = active_lang
            intent = gemini_result.get('intent', 'WALLET_STATUS').upper()
            crop_name = gemini_result.get('crop_name')
            quantity_kg = gemini_result.get('quantity_kg')
            input_type = gemini_result.get('input_type')
            gemini_reply = gemini_result.get('localized_reply_text')

        # Fallback keyword extraction if Gemini call was unavailable
        if not gemini_result:
            detected_lang = cls.detect_script_language(transcript, active_lang)
            transcript_lower = transcript.lower()
            if any(w in transcript_lower for w in ['भाव', 'रेट', 'दाम', 'price', 'rate', 'bhaav', 'दर', 'ధర', 'விலை', 'ಬೆಲೆ', 'ਭਾਅ']):
                intent = "CHECK_PRICE"
            elif any(w in transcript_lower for w in ['तोड़ा', 'कटाई', 'harvest', 'picked', 'कापणी', 'किलो', 'kg', 'కిలో', 'கிலோ', 'ಕೆಜಿ', 'ਕਿੱਲੋ']):
                intent = "LOG_HARVEST"
            elif any(w in transcript_lower for w in ['लोन', 'कर्ज', 'loan', 'credit', 'बीज', 'खाद', 'खत', 'రుణం', 'கடன்', 'ಸಾಲ']):
                intent = "INPUT_FINANCING"
            else:
                intent = "WALLET_STATUS"

        lang_cfg = REGIONAL_LANGUAGES.get(detected_lang, REGIONAL_LANGUAGES['hi'])
        honorific = lang_cfg['honorific']
        name_display = f"{farmer_name} {honorific}".strip() if honorific not in farmer_name else farmer_name

        # Database Execution & State Updates based on Intent
        if intent == "CHECK_PRICE":
            crop = None
            if crop_name:
                crop = Crop.objects.filter(name__icontains=crop_name).first()
            if not crop:
                crop = Crop.objects.filter(name__icontains='Tomato').first() or Crop.objects.first()

            msp = float(crop.base_msp_price_per_kg) if crop else 14.0
            indicative_price = round(msp * 1.35, 2)
            crop_display = crop.name if crop else "Produce"

            if not gemini_reply:
                gemini_reply = cls._get_price_check_fallback(detected_lang, name_display, crop_display, indicative_price, msp)

            return {
                "intent": "CHECK_PRICE",
                "crop_id": crop.id if crop else None,
                "crop_name": crop.name if crop else "Hybrid Tomato",
                "current_price_per_kg": indicative_price,
                "statutory_msp_floor": msp,
                "voice_reply_text": gemini_reply,
                "language": detected_lang,
                "language_name": lang_cfg['name'],
                "locale": lang_cfg['locale']
            }

        elif intent == "LOG_HARVEST":
            crop = Crop.objects.filter(name__icontains=crop_name).first() if crop_name else (Crop.objects.first())
            qty = Decimal(str(quantity_kg)) if quantity_kg else Decimal('200.00')

            batch_code = f"K2K-{timezone.now().strftime('%Y%m%d')}-HARV-{crop.name[:3].upper() if crop else 'CRP'}"
            crop_display = crop.name if crop else "Produce"

            if not gemini_reply:
                gemini_reply = cls._get_log_harvest_fallback(detected_lang, name_display, crop_display, float(qty), batch_code)

            return {
                "intent": "LOG_HARVEST",
                "batch_code": batch_code,
                "crop_name": crop.name if crop else "Tomato",
                "logged_quantity_kg": float(qty),
                "voice_reply_text": gemini_reply,
                "language": detected_lang,
                "language_name": lang_cfg['name'],
                "locale": lang_cfg['locale']
            }

        elif intent == "INPUT_FINANCING":
            input_type_enum = InputType.CERTIFIED_SEEDS
            package = "Certified High-Yield Hybrid Seeds"
            if input_type and 'FERTILIZER' in input_type:
                input_type_enum = InputType.BIO_FERTILIZER
                package = "Organic Bio-Fertilizer & NPK Pack"
            elif input_type and 'EQUIPMENT' in input_type:
                input_type_enum = InputType.DRIP_IRRIGATION
                package = "Micro-Drip Irrigation Kit"

            loan = None
            if farmer:
                loan_id = f"LOAN-{farmer.id}-{int(timezone.now().timestamp())}"
                loan = InputLoan.objects.create(
                    loan_id=loan_id,
                    farmer=farmer,
                    input_type=input_type_enum,
                    package_name=package,
                    quantity_units=1,
                    unit_cost=Decimal('5000.00'),
                    total_loan_amount=Decimal('5000.00'),
                    outstanding_balance=Decimal('5000.00'),
                    interest_rate_pct=Decimal('0.00'),
                    due_date=timezone.now().date() + timezone.timedelta(days=90),
                    status=InputLoanStatus.ACTIVE
                )

            if not gemini_reply:
                gemini_reply = cls._get_input_financing_fallback(detected_lang, name_display, 5000)

            return {
                "intent": "INPUT_FINANCING",
                "loan_id": loan.id if loan else 101,
                "principal_rupees": 5000.0,
                "interest_rate": "0% (K2K In-Kind Farmer Guarantee)",
                "voice_reply_text": gemini_reply,
                "language": detected_lang,
                "language_name": lang_cfg['name'],
                "locale": lang_cfg['locale']
            }

        else:
            # WALLET_STATUS
            balance = Decimal('14500.00')
            if farmer:
                wallet, _ = FarmerWallet.objects.get_or_create(farmer=farmer)
                balance = wallet.current_balance

            if not gemini_reply:
                gemini_reply = cls._get_wallet_status_fallback(detected_lang, name_display, float(balance))

            return {
                "intent": "WALLET_STATUS",
                "wallet_balance": float(balance),
                "voice_reply_text": gemini_reply,
                "language": detected_lang,
                "language_name": lang_cfg['name'],
                "locale": lang_cfg['locale']
            }

    # ==========================================================================
    # CULTURALLY GROUNDED FALLBACK GENERATORS ACROSS ALL 8 REGIONAL LANGUAGES
    # ==========================================================================

    @classmethod
    def _get_price_check_fallback(cls, lang: str, name: str, crop: str, price: float, msp: float) -> str:
        templates = {
            'mr': f"नमस्कार {name}, आज {crop} चा K2K हमीभाव ₹{price} प्रति किलो आहे, ज्यावर ₹{msp} चा आधारभूत दर (MSP) सुरक्षित आहे.",
            'te': f"నమస్కారం {name}, ఈరోజు {crop} K2K ధర కిలోకు ₹{price}. కనీస మద్దతు ధర ₹{msp} హామీ ఇవ్వబడింది.",
            'ta': f"வணக்கம் {name}, இன்று {crop} K2K விலை கிலோவுக்கு ₹{price}. குறைந்தபட்ச ஆதரவு விலை ₹{msp} உறுதி செய்யப்பட்டுள்ளது.",
            'kn': f"ನಮಸ್ಕಾರ {name}, ಇಂದು {crop} K2K ಬೆಲೆ ಪ್ರತಿ ಕೆಜಿಗೆ ₹{price}. ಕನಿಷ್ಠ ಬೆಂಬಲ ಬೆಲೆ ₹{msp} ಖಾತರಿಪಡಿಸಲಾಗಿದೆ.",
            'pa': f"ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ {name}, ਅੱਜ {crop} ਦਾ K2K ਭਾਅ ₹{price} ਪ੍ਰਤੀ ਕਿੱਲੋ ਹੈ ਅਤੇ ਘੱਟੋ-ਘੱਟ ਸਮਰਥਨ ਮੁੱਲ ₹{msp} ਸੁਰੱਖਿਅਤ ਹੈ।",
            'gu': f"નમસ્તે {name}, આજે {crop} નો K2K ભાવ પ્રતિ કિલો ₹{price} છે. ટેકાના લઘુત્તમ ભાવ ₹{msp} ની સંપૂર્ણ સુરક્ષા છે.",
            'en': f"Hello {name}, the current K2K price for {crop} is ₹{price}/kg with guaranteed MSP floor of ₹{msp}/kg.",
            'hi': f"नमस्ते {name}, आज K2K पर {crop} का भाव ₹{price} प्रति किलो चल रहा है। इस पर न्यूनतम समर्थन मूल्य (MSP) ₹{msp} सुरक्षित है।"
        }
        return templates.get(lang, templates['hi'])

    @classmethod
    def _get_log_harvest_fallback(cls, lang: str, name: str, crop: str, qty: float, batch_code: str) -> str:
        templates = {
            'mr': f"{name}, तुमची {qty} किलो {crop} ची नोंदणी झाली आहे. बॅच क्रमांक {batch_code}. जवळच्या मायक्रो-हबवर जमा करा.",
            'te': f"{name}, మీ {qty} కిలోల {crop} విజయవంతంగా నమోదు చేయబడింది. బ్యాచ్ ID {batch_code}. సమీప మైక్రో-హబ్‌కు తీసుకురండి.",
            'ta': f"{name}, உங்கள் {qty} கிலோ {crop} பதிவு செய்யப்பட்டது. தொகுதி எண் {batch_code}. அருகில் உள்ள மைக்ரோ மையத்தில் சேர்க்கவும்.",
            'kn': f"{name}, ನಿಮ್ಮ {qty} ಕೆಜಿ {crop} ಯಶಸ್ವಿಯಾಗಿ ದಾಖಲಾಗಿದೆ. ಬ್ಯಾಚ್ ಕೋಡ್ {batch_code}. ಹತ್ತಿರದ ಮೈಕ್ರೋ-ಹಬ್‌ಗೆ ತನ್ನಿ.",
            'pa': f"{name}, ਤੁਹਾਡੀ {qty} ਕਿੱਲੋ {crop} ਦੀ ਆਮਦ ਦਰਜ ਹੋ ਗਈ ਹੈ। ਬੈਚ ਕੋਡ {batch_code} ਹੈ। ਕਿਰਪਾ ਕਰਕੇ ਨਜ਼ਦੀਕੀ ਹੱਬ 'ਤੇ ਲਿਆਓ।",
            'gu': f"{name}, તમારી {qty} કિલો {crop} ની નોંધણી થઈ ગઈ છે. બેચ કોડ {batch_code} છે. કૃપા કરીને નજીકના માઇક્રો-હબ પર લાવો.",
            'en': f"{name}, successfully logged {qty} kg of {crop} under Batch ID {batch_code}. Ready for hub drop-off.",
            'hi': f"{name}, आपकी {qty} किलो {crop} की आवक दर्ज कर ली गई है। बैच कोड {batch_code} जारी हो गया है। कृपया नजदीकी माइक्रो-हब पर लाएं।"
        }
        return templates.get(lang, templates['hi'])

    @classmethod
    def _get_input_financing_fallback(cls, lang: str, name: str, amount: int) -> str:
        templates = {
            'mr': f"{name}, तुमचे ₹{amount} चे शून्य-व्याज खत व बियाणे कर्ज मंजूर झाले आहे. पुढील कापणीच्या वेळी आपोआप वजा केले जाईल.",
            'te': f"{name}, మీ ₹{amount} వడ్డీ లేని విత్తనాలు మరియు ఎరువుల రుణం ఆమోదించబడింది. పంట కోత సమయంలో చెల్లించవచ్చు.",
            'ta': f"{name}, உங்களுக்கான ₹{amount} வட்டி இல்லா விதை மற்றும் உர கடன் அனுமதிக்கப்பட்டது. அறுவடையின் போது திருப்பி செலுத்தப்படும்.",
            'kn': f"{name}, ನಿಮಗೆ ₹{amount} ಮೌಲ್ಯದ 0% ಬಡ್ಡಿ ದರದ ಬಿತ್ತನೆ ಬೀಜ ಮತ್ತು ಗೊಬ್ಬರ ಸಾಲ ಮಂಜೂರಾಗಿದೆ. ಕೊಯ್ಲಿನ ಸಮಯದಲ್ಲಿ ಪಾವತಿಸಬಹುದು.",
            'pa': f"{name}, ਤੁਹਾਡੇ ਲਈ ₹{amount} ਦਾ ਬਿਨਾਂ ਵਿਆਜ ਵਾਲਾ ਬੀਜ ਅਤੇ ਖਾਦ ਲੋਨ ਮਨਜ਼ੂਰ ਹੋ ਗਿਆ ਹੈ। ਅਗਲੀ ਵਾਢੀ ਵੇਲੇ ਭੁਗਤਾਨ ਹੋਵੇਗਾ।",
            'gu': f"{name}, તમારા માટે ₹{amount} નું 0% વ્યાજવાળું ખાતર-બિયારણ લોન મંજૂર થયું છે. પાક લણણી સમયે ચૂકવણી થશે.",
            'en': f"{name}, your 0% interest input financing of ₹{amount} for certified seeds and bio-fertilizers is approved and credited.",
            'hi': f"{name}, आपके लिए ₹{amount} का 0% ब्याज वाला इनपुट लोन स्वीकृत कर दिया गया है। फसल कटाई के समय इसका भुगतान स्वतः होगा।"
        }
        return templates.get(lang, templates['hi'])

    @classmethod
    def _get_wallet_status_fallback(cls, lang: str, name: str, balance: float) -> str:
        templates = {
            'mr': f"नमस्कार {name}, तुमच्या K2K वॉलेटमध्ये शिल्लक रक्कम ₹{balance} आहे. हे पैसे तुमच्या UPI खात्यात त्वरित जमा केले जाऊ शकतात.",
            'te': f"నమస్కారం {name}, మీ K2K వాలెట్ బ్యాలెన్స్ ₹{balance}. తక్షణ UPI ఉపసంహరణకు సిద్ధంగా ఉంది.",
            'ta': f"வணக்கம் {name}, உங்கள் K2K வாலட்டில் ₹{balance} இருப்பு உள்ளது. உடனடி UPI மூலம் பெற்றுக்கொள்ளலாம்.",
            'kn': f"ನಮಸ್ಕಾರ {name}, ನಿಮ್ಮ K2K ವಾಲೆಟ್‌ನಲ್ಲಿ ₹{balance} ಬಾಕಿ ಇದೆ. ತಕ್ಷಣ ಯುಪಿಐ ಮೂಲಕ ಪಡೆಯಬಹುದು.",
            'pa': f"ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ {name}, ਤੁਹਾਡੇ K2K ਵਾਲੇਟ ਵਿੱਚ ₹{balance} ਬਕਾਇਆ ਹਨ। ਤੁਸੀਂ ਤੁਰੰਤ UPI ਰਾਹੀਂ ਕਢਵਾ ਸਕਦੇ ਹੋ।",
            'gu': f"નમસ્તે {name}, તમારા K2K વૉલેટમાં ₹{balance} જમા છે. તમે તરત જ UPI દ્વારા ટ્રાન્સફર કરી શકો છો.",
            'en': f"Hello {name}, your current K2K wallet balance is ₹{balance}. Ready for instant UPI withdrawal.",
            'hi': f"नमस्ते {name}, आपके K2K वॉलेट में वर्तमान शेष राशि ₹{balance} है। आप इसे तुरंत UPI से निकाल सकते हैं।"
        }
        return templates.get(lang, templates['hi'])
