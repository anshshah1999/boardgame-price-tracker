import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime
import time

st.set_page_config(page_title="Boardgame Price Tracker", page_icon="🎲", layout="wide")

GAMES_FILE = "games.csv"
CACHE_FILE = "price_cache.json"
EXCHANGE_API_URL = "https://api.exchangerate-api.com/v4/latest/USD"

@st.cache_resource
def get_session_state():
    if 'last_refresh' not in st.session_state:
        st.session_state.last_refresh = None
    if 'cache_data' not in st.session_state:
        st.session_state.cache_data = load_price_cache()
    return st.session_state

@st.cache_data(ttl=3600)
def get_currency_rates():
    try:
        response = requests.get(EXCHANGE_API_URL, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return {
                'INR': data['rates'].get('INR', 82.5),
                'GBP': data['rates'].get('GBP', 0.79),
                'CAD': data['rates'].get('CAD', 1.36),
                'AUD': data['rates'].get('AUD', 1.53),
                'timestamp': datetime.now().isoformat()
            }
    except:
        pass
    return {'INR': 82.5, 'GBP': 0.79, 'CAD': 1.36, 'AUD': 1.53, 'timestamp': datetime.now().isoformat()}

def scrape_board_game_oracle(game_name, region="USA"):
    try:
        search_url = f"https://www.boardgameoracle.com/search?q={game_name}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(search_url, headers=headers, timeout=5)
        soup = BeautifulSoup(response.content, 'html.parser')
        price_elements = soup.find_all('span', class_=['price', 'product-price'])
        if price_elements:
            import re
            numbers = re.findall(r'\d+\.?\d*', price_elements[0].get_text(strip=True))
            if numbers:
                return {'price': float(numbers[0]), 'found': True, 'timestamp': datetime.now().isoformat()}
        return {'price': None, 'found': False, 'timestamp': datetime.now().isoformat()}
    except:
        return {'price': None, 'found': False, 'timestamp': datetime.now().isoformat()}

def load_games():
    return pd.read_csv(GAMES_FILE) if os.path.exists(GAMES_FILE) else pd.DataFrame(columns=['Game Name', 'Added Date'])

def save_games(df):
    df.to_csv(GAMES_FILE, index=False)

def load_price_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_price_cache(cache):
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache, f, indent=2)
    st.session_state.cache_data = cache

get_session_state()
st.sidebar.title("🎲 Boardgame Price Tracker")

tab1, tab2, tab3, tab4, tab5 = st.tabs(["Games", "Analysis", "USA", "UK", "Settings"])

with tab1:
    st.header("Manage Games")
    col1, col2 = st.columns([3, 1])
    new_game = col1.text_input("Game name:", placeholder="e.g., Catan")
    if col2.button("Add"):
        if new_game.strip():
            df = load_games()
            if new_game not in df['Game Name'].values:
                new_df = pd.concat([df, pd.DataFrame({'Game Name': [new_game], 'Added Date': [datetime.now().strftime('%Y-%m-%d')]})], ignore_index=True)
                save_games(new_df)
                st.success(f"Added {new_game}")
                st.rerun()

    df = load_games()
    if not df.empty:
        st.dataframe(df, use_container_width=True)
        c1, c2, c3 = st.columns(3)
        if c1.button("Refresh Prices"):
            st.session_state.last_refresh = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            st.success("Prices refreshed!")
        if c2.button("Export"):
            st.download_button("Download CSV", df.to_csv(index=False), "games.csv", "text/csv")
        if c3.button("Clear"):
            if os.path.exists(GAMES_FILE):
                os.remove(GAMES_FILE)
            st.success("Cleared!")
            st.rerun()

with tab2:
    st.header("Price Analysis")
    df = load_games()
    if not df.empty:
        st.info(f"Total games: {len(df)}")
        if st.session_state.last_refresh:
            st.caption(f"Last refresh: {st.session_state.last_refresh}")
    else:
        st.info("Add games to see analysis")

with tab3:
    st.header("USA Prices")
    df = load_games()
    if not df.empty:
        st.metric("Region", "USA 🇺🇸")
        st.info("Select games from the Games tab to see prices")
    else:
        st.info("Add games first")

with tab4:
    st.header("UK Prices")
    df = load_games()
    if not df.empty:
        st.metric("Region", "UK 🇬🇧")
        st.info("Select games from the Games tab to see prices")
    else:
        st.info("Add games first")

with tab5:
    st.header("Settings")
    cache = load_price_cache()
    st.metric("Cached games", len(cache))
    if st.button("Clear Cache"):
        save_price_cache({})
        st.success("Cache cleared!")

    rates = get_currency_rates()
    col1, col2 = st.columns(2)
    col1.metric("USD to INR", f"₹{rates['INR']:.2f}")
    col2.metric("Last update", rates['timestamp'][:10])
