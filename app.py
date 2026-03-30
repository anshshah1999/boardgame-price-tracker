import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime
import time

# Page configuration
st.set_page_config(
    page_title="Boardgame Price Tracker",
    page_icon="🎲",
    layout="wide",
    initial_sidebar_state="expanded"
)

# File paths
GAMES_FILE = "games.csv"
CACHE_FILE = "price_cache.json"

# Board Game Oracle URLs by region
REGION_URLS = {
    "USA": "https://www.boardgameoracle.com/games?region=us",
    "UK": "https://www.boardgameoracle.com/games?region=gb",
    "Canada": "https://www.boardgameoracle.com/games?region=ca",
    "Australia": "https://www.boardgameoracle.com/games?region=au"
}

# Currency exchange API
EXCHANGE_API_URL = "https://api.exchangerate-api.com/v4/latest/USD"

@st.cache_resource
def get_session_state():
    """Initialize session state variables"""
    if 'last_refresh' not in st.session_state:
        st.session_state.last_refresh = None
    if 'cache_data' not in st.session_state:
        st.session_state.cache_data = load_price_cache()
    return st.session_state

@st.cache_data(ttl=3600)
def get_currency_rates():
    """Fetch current currency exchange rates"""
    try:
        response = requests.get(EXCHANGE_API_URL, timeout=5)
        if response.status_code == 200:
            data = response.json()
            inr_rate = data['rates'].get('INR', 82.5)
            gbp_rate = data['rates'].get('GBP', 0.79)
            cad_rate = data['rates'].get('CAD', 1.36)
            aud_rate = data['rates'].get('AUD', 1.53)
            return {
                'INR': inr_rate,
                'GBP': gbp_rate,
                'CAD': cad_rate,
                'AUD': aud_rate,
                'timestamp': datetime.now().isoformat()
            }
    except:
        pass

    # Fallback rates
    return {
        'INR': 82.5,
        'GBP': 0.79,
        'CAD': 1.36,
        'AUD': 1.53,
        'timestamp': datetime.now().isoformat()
    }

def scrape_board_game_oracle(game_name, region="USA"):
    """Scrape Board Game Oracle for game prices"""
    try:
        region_code = region.upper()
        search_url = f"https://www.boardgameoracle.com/search?q={game_name}&region={region_code[:2].lower()}"

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        response = requests.get(search_url, headers=headers, timeout=5)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        # Try to find price information
        price_elements = soup.find_all('span', class_=['price', 'product-price'])

        if price_elements:
            price_text = price_elements[0].get_text(strip=True)
            # Extract numerical value
            import re
            numbers = re.findall(r'\d+\.?\d*', price_text)
            if numbers:
                return {
                    'price': float(numbers[0]),
                    'currency': 'USD' if region == 'USA' else 'GBP' if region == 'UK' else 'CAD' if region == 'Canada' else 'AUD',
                    'found': True,
                    'timestamp': datetime.now().isoformat()
                }

        return {'price': None, 'found': False, 'timestamp': datetime.now().isoformat()}

    except Exception as e:
        st.warning(f"Could not fetch from {region}: {str(e)}")
        return {'price': None, 'found': False, 'error': str(e), 'timestamp': datetime.now().isoformat()}

def load_games():
    """Load games from CSV file"""
    if os.path.exists(GAMES_FILE):
        try:
            return pd.read_csv(GAMES_FILE)
        except:
            return pd.DataFrame(columns=['Game Name', 'Added Date'])
    return pd.DataFrame(columns=['Game Name', 'Added Date'])

def save_games(df):
    """Save games to CSV file"""
    df.to_csv(GAMES_FILE, index=False)

def load_price_cache():
    """Load price cache from JSON file"""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_price_cache(cache):
    """Save price cache to JSON file"""
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache, f, indent=2)
    st.session_state.cache_data = cache

def get_game_data_with_analysis(game_name):
    """Fetch and analyze game pricing across all regions"""
    cache = st.session_state.cache_data
    cache_key = game_name.lower()

    # Check cache freshness (1 hour)
    if cache_key in cache:
        cached_time = datetime.fromisoformat(cache[cache_key].get('timestamp', '2000-01-01'))
        if (datetime.now() - cached_time).seconds < 3600:
            return cache[cache_key]

    data = {}
    rates = get_currency_rates()

    for region in ['USA', 'UK', 'Canada', 'Australia']:
        time.sleep(0.5)  # Rate limiting
        result = scrape_board_game_oracle(game_name, region)

        if result['found']:
            price_usd = result['price']
            if region == 'UK':
                price_usd = result['price'] / rates['GBP']
            elif region == 'Canada':
                price_usd = result['price'] / rates['CAD']
            elif region == 'Australia':
                price_usd = result['price'] / rates['AUD']

            price_inr = price_usd * rates['INR']

            data[region] = {
                'price_local': result['price'],
                'currency': result['currency'],
                'price_usd': round(price_usd, 2),
                'price_inr': round(price_inr, 2)
            }
        else:
            data[region] = {'price_local': None, 'found': False}

    # Find best prices
    valid_prices = {r: d['price_inr'] for r, d in data.items() if 'price_inr' in d}

    if valid_prices:
        best_region = min(valid_prices, key=valid_prices.get)
        cheapest_inr = valid_prices[best_region]
        data['best_region'] = best_region
        data['cheapest_inr'] = cheapest_inr

    data['timestamp'] = datetime.now().isoformat()

    # Cache it
    cache[cache_key] = data
    save_price_cache(cache)

    return data

def get_best_games_from_country(games_df, country, top_n=10):
    """Get best value games from a specific country"""
    results
