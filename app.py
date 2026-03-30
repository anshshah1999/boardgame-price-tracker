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
    results = []

    for game in games_df['Game Name'].unique():
        data = get_game_data_with_analysis(game)
        if country in data and 'price_inr' in data[country]:
            results.append({
                'Game': game,
                'Price (INR)': data[country]['price_inr'],
                'Best Region': data.get('best_region', 'N/A'),
                'Savings': round(data[country]['price_inr'] - data.get('cheapest_inr', 0), 2)
            })

    if results:
        results_df = pd.DataFrame(results).sort_values('Price (INR)')
        return results_df.head(top_n)
    return pd.DataFrame()

# Initialize session
get_session_state()

# Sidebar
st.sidebar.title("🎲 Boardgame Price Tracker")
st.sidebar.markdown("---")

# Main tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Games Management",
    "Full Analysis",
    "USA Shortlist",
    "UK Shortlist",
    "Settings"
])

# TAB 1: Games Management
with tab1:
    st.header("Manage Your Games List")

    col1, col2 = st.columns([3, 1])
    with col1:
        new_game = st.text_input("Enter game name to add:", placeholder="e.g., Catan, Ticket to Ride")
    with col2:
        if st.button("➕ Add Game", use_container_width=True):
            if new_game.strip():
                games_df = load_games()
                if new_game not in games_df['Game Name'].values:
                    new_row = pd.DataFrame({
                        'Game Name': [new_game],
                        'Added Date': [datetime.now().strftime('%Y-%m-%d')]
                    })
                    games_df = pd.concat([games_df, new_row], ignore_index=True)
                    save_games(games_df)
                    st.success(f"✅ Added {new_game}")
                    st.rerun()
                else:
                    st.warning(f"⚠️ {new_game} already in list")

    st.markdown("---")

    games_df = load_games()
    if not games_df.empty:
        st.subheader("Your Games")
        display_df = games_df.copy()
        display_df.index = display_df.index + 1

        st.dataframe(display_df, use_container_width=True)

        col1, col2, col3 = st.columns([2, 2, 2])

        with col1:
            if st.button("🔄 Refresh All Prices", use_container_width=True):
                st.session_state.last_refresh = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.info("Fetching prices... This may take a few minutes.")
                progress = st.progress(0)

                for idx, game in enumerate(games_df['Game Name']):
                    get_game_data_with_analysis(game)
                    progress.progress((idx + 1) / len(games_df))

                st.success("✅ Prices updated!")
                st.rerun()

        with col2:
            if st.button("📥 Export to CSV", use_container_width=True):
                csv = games_df.to_csv(index=False)
                st.download_button(
                    label="Download CSV",
                    data=csv,
                    file_name="boardgame_list.csv",
                    mime="text/csv"
                )

        with col3:
            if st.button("🗑️ Clear All Data", use_container_width=True):
                if st.checkbox("I'm sure"):
                    os.remove(GAMES_FILE) if os.path.exists(GAMES_FILE) else None
                    os.remove(CACHE_FILE) if os.path.exists(CACHE_FILE) else None
                    st.success("✅ Data cleared")
                    st.rerun()
    else:
        st.info("📌 No games added yet. Add your first game above!")

# TAB 2: Full Analysis
with tab2:
    st.header("Full Price Analysis")
    games_df = load_games()

    if not games_df.empty:
        st.subheader("Prices Across All Regions")

        all_data = []
        progress = st.progress(0)

        for idx, game in enumerate(games_df['Game Name']):
            data = get_game_data_with_analysis(game)

            row = {'Game': game}
            for region in ['USA', 'UK', 'Canada', 'Australia']:
                if region in data and 'price_inr' in data[region]:
                    row[f"{region} (INR)"] = f"₹{data[region]['price_inr']:.2f}"
                else:
                    row[f"{region} (INR)"] = "N/A"

            if 'best_region' in data:
                row['Best Deal'] = f"{data['best_region']} @ ₹{data['cheapest_inr']:.2f}"
            else:
                row['Best Deal'] = "N/A"

            all_data.append(row)
            progress.progress((idx + 1) / len(games_df))

        analysis_df = pd.DataFrame(all_data)
        st.dataframe(analysis_df, use_container_width=True)

        # Summary statistics
        st.markdown("---")
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Total Games Tracked", len(games_df))
        with col2:
            refresh_time = st.session_state.last_refresh.strftime("%Y-%m-%d %H:%M:%S") if st.session_state.last_refresh else "Never"
st.metric("Last Refresh", refresh_time)
        with col3:
            rates = get_currency_rates()
            st.metric("INR Rate (USD)", f"₹{rates['INR']:.2f}")
    else:
        st.info("📌 Add games to see analysis")

# TAB 3: USA Shortlist
with tab3:
    st.header("Best Prices in USA")
    games_df = load_games()

    if not games_df.empty:
        col1, col2 = st.columns([3, 1])
        with col1:
            top_n = st.slider("Show top N games:", 5, len(games_df), 10)
        with col2:
            st.metric("Region", "USA 🇺🇸")

        usa_results = get_best_games_from_country(games_df, 'USA', top_n)
        if not usa_results.empty:
            st.dataframe(usa_results, use_container_width=True)
        else:
            st.warning("No pricing data available for USA")
    else:
        st.info("📌 Add games first")

# TAB 4: UK Shortlist
with tab4:
    st.header("Best Prices in UK")
    games_df = load_games()

    if not games_df.empty:
        col1, col2 = st.columns([3, 1])
        with col1:
            top_n = st.slider("Show top N games:", 5, len(games_df), 10, key="uk_slider")
        with col2:
            st.metric("Region", "UK 🇬🇧")

        uk_results = get_best_games_from_country(games_df, 'UK', top_n)
        if not uk_results.empty:
            st.dataframe(uk_results, use_container_width=True)
        else:
            st.warning("No pricing data available for UK")
    else:
        st.info("📌 Add games first")

# TAB 5: Settings
with tab5:
    st.header("⚙️ Settings")

    st.subheader("Cache Status")
    cache = load_price_cache()
    st.metric("Cached Games", len(cache))

    if st.button("Clear Price Cache", use_container_width=True):
        save_price_cache({})
        st.success("✅ Cache cleared")
        st.rerun()

    st.markdown("---")

    st.subheader("About")
    st.info(
        "Boardgame Price Tracker automatically fetches prices from Board Game Oracle across "
        "USA, UK, Canada, and Australia, converting all prices to INR for easy comparison. "
        "Prices are cached for 1 hour to reduce API calls."
    )

    st.subheader("Exchange Rates (Last Updated)")
    rates = get_currency_rates()
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("USD to INR", f"₹{rates['INR']:.2f}")
    with col2:
        st.metric("GBP to INR", f"₹{rates['GBP'] * rates['INR']:.2f}")
    with col3:
        st.metric("CAD to INR", f"₹{rates['CAD'] * rates['INR']:.2f}")
    with col4:
        st.metric("AUD to INR", f"₹{rates['AUD'] * rates['INR']:.2f}")

    st.caption(f"Updated: {rates['timestamp']}")
